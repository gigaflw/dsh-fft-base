// 一次性「免费 Key」提示的判定与设备级标记。
//
// 这个 feature 的关键风险全在「该不该弹」上：弹早了、弹给已配 Key 的人、
// 或每次都弹，都比不弹更糟。所以判定逻辑被抽成纯函数，在这里逐条钉住；
// 渲染层只负责把模态框摆出去。

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFile } from 'node:fs/promises'
import {
  FREE_KEY_NOTICE_ID, FREE_KEY_NOTICE_SLOT, isViewIdle, shouldShowNotice,
} from '../lib/features/free-key-notice/decision.js'
import { browserNoticeStorage, readNoticeSeen, writeNoticeSeen } from '../lib/features/free-key-notice/storage.js'
import { FREE_KEY_NOTICE_STORAGE_KEY, FTSHARE_API_KEY_APPLY_URL } from '../lib/contract.js'

/** 内存存储，替身 `localStorage`；`fail` 模拟隐私模式下的抛异常。 */
function memoryStorage(options = {}) {
  const data = new Map(Object.entries(options.seed ?? {}))
  return {
    data,
    getItem: key => { if (options.fail) throw new Error('blocked'); return data.get(key) ?? null },
    setItem: (key, value) => { if (options.fail) throw new Error('blocked'); data.set(key, value) },
  }
}

test('the notice only shows for a confirmed unconfigured key on an idle view', () => {
  // 唯一该弹的组合。
  assert.equal(shouldShowNotice({ seen: false, configured: false, viewIdle: true }), true)

  // 已看过：永远不弹，哪怕其余条件都满足。
  assert.equal(shouldShowNotice({ seen: true, configured: false, viewIdle: true }), false)
  // 已配置 Key：不打扰。
  assert.equal(shouldShowNotice({ seen: false, configured: true, viewIdle: true }), false)
  // 状态未知（异步还没读回来）：不弹 —— 否则已配 Key 的用户每次启动都被闪一下。
  assert.equal(shouldShowNotice({ seen: false, configured: undefined, viewIdle: true }), false)
  // 主视图还被有内容的会话占着：等到空下来再弹。
  assert.equal(shouldShowNotice({ seen: false, configured: false, viewIdle: false }), false)
})

test('the view counts as idle only when the main session is blank or absent', () => {
  assert.equal(isViewIdle({ phase: 'ready', byId: {} }), true)
  assert.equal(isViewIdle({ phase: 'ready', byId: { a: { blank: true, retainedBy: { mainView: 1 } } } }), true)
  assert.equal(isViewIdle({ phase: 'ready', byId: { a: { blank: false, retainedBy: { mainView: 1 } } } }), false)
  // 别的会话有内容不算数：只看主视图占用的那一个。
  assert.equal(isViewIdle({ phase: 'ready', byId: { a: { blank: true, retainedBy: { mainView: 1 } }, b: { blank: false } } }), true)
  // 会话层还没 ready 时不弹。
  assert.equal(isViewIdle({ phase: 'loading', byId: {} }), false)
})

test('the seen flag is device-level: written once, read back, and degrades safely', () => {
  const storage = memoryStorage()
  assert.equal(readNoticeSeen(storage, FREE_KEY_NOTICE_STORAGE_KEY), false)
  assert.equal(writeNoticeSeen(storage, FREE_KEY_NOTICE_STORAGE_KEY), true)
  assert.equal(storage.data.get(FREE_KEY_NOTICE_STORAGE_KEY), '1')
  assert.equal(readNoticeSeen(storage, FREE_KEY_NOTICE_STORAGE_KEY), true)

  // 存储缺失（非浏览器环境）：按没看过处理，写入静默失败，不抛。
  assert.equal(readNoticeSeen(undefined, FREE_KEY_NOTICE_STORAGE_KEY), false)
  assert.equal(writeNoticeSeen(undefined, FREE_KEY_NOTICE_STORAGE_KEY), false)

  // 隐私模式：读写都抛异常，但函数本身不能把设置页带崩。
  const blocked = memoryStorage({ fail: true })
  assert.equal(readNoticeSeen(blocked, FREE_KEY_NOTICE_STORAGE_KEY), false)
  assert.equal(writeNoticeSeen(blocked, FREE_KEY_NOTICE_STORAGE_KEY), false)

  // 取存储本身失败（例如 globalThis.localStorage 抛 SecurityError）也不能抛。
  assert.doesNotThrow(() => browserNoticeStorage())
})

test('the notice is registered on the frame-wide overlay, not inside the settings page', async () => {
  // id 必须独占：槽位按 id 去重，复用宿主的 id 会顶掉别人的浮层。
  assert.equal(FREE_KEY_NOTICE_ID, 'ftshare.free-key-notice')
  assert.equal(FREE_KEY_NOTICE_SLOT, 'shell.overlay')

  const source = await readFile(new URL('../src/features/free-key-notice/index.ts', import.meta.url), 'utf8')
  // 必须先等槽位被声明，启动早期直接 register 会抛。
  assert.match(source, /slots\.inject\(FREE_KEY_NOTICE_SLOT/)
  // 弹窗里的跳转必须复用同一个常量：地址分叉会让归因失效。
  assert.doesNotMatch(source, /ftai\.chat/)

  const card = await readFile(new URL('../src/features/free-key-notice/card.tsx', import.meta.url), 'utf8')
  assert.doesNotMatch(card, /ftai\.chat/)
  assert.match(card, /FTSHARE_API_KEY_APPLY_URL/)
  // 新窗口打开外链；桌面版主窗会把它交给系统浏览器。
  assert.match(card, /target="_blank"/)

  // 用户可见文案固定为一句；标题是「免费获取 Key」，主入口是「去获取」。
  assert.match(card, /<strong>免费获取 Key<\/strong>/)
  assert.match(card, /海量金融数据，一次配置长期使用/)
  assert.match(card, />去获取</)
  assert.doesNotMatch(card, />去申请</)

  // 主入口的底色是品牌黄 70%（用户定的档位）；改成实心或别的比例都要先过这条。
  const noticeStyles = await readFile(new URL('../src/features/free-key-notice/styles.ts', import.meta.url), 'utf8')
  assert.match(noticeStyles, /background:color-mix\(in srgb,var\(--ft-accent,#f0c433\) 70%,transparent\)/)

  // 额度数字是推测值，任何用户可见的地方都不能出现它（含各种写法）。
  // 命中这条说明有人把上游原文或内部口径抄进了提示文案。
  assert.doesNotMatch(source, /500/)
  // 只检查文案字符（`font-weight:500` 这类样式数值不算额度表述）。
  assert.doesNotMatch(card, /500\s*次/)
  assert.doesNotMatch(source, /500\s*次/)
  // 「24 小时」「匿名额度」这类细化口径同样不该出现在用户面前。
  assert.doesNotMatch(card, /24\s*小时|匿名额度/)
})

test('the notice link matches the settings card so one funnel sees both entries', () => {
  const url = new URL(FTSHARE_API_KEY_APPLY_URL)
  assert.equal(url.searchParams.get('utm_source'), 'dsh-fft')
  assert.equal(url.searchParams.get('tab'), 'api-key')
})
