/**
 * 一次性提示：还没配置 API Key 的用户，去获取免费的 FTShare Key。
 *
 * 三个设计决定：
 *
 * 1. **左下角、不阻塞**。它是提示，不是必须处理的阻断：不盖遮罩、不抢焦点、
 *    不打断正在发生的事，12 秒后自己淡出（鼠标悬停时暂停计时）。用 `Modal`
 *    会遮住整个界面，代价太大。
 * 2. **只在确认「没配 Key」时出现**。凭据状态异步读来，没读到时一律不出现，
 *    否则配了 Key 的用户每次启动都会被闪一下。
 * 3. **设备级只出现一次**。首次出现就写 `localStorage` 标记（见 `./storage.ts`），
 *    不等用户点按钮——否则自动消失后标记不落盘，下次启动又会打扰。
 *
 * 挂载在宿主框架级的 `shell.overlay` 槽上（`ui-layout` 的 AppFrame 常驻渲染），
 * 不在设置页里：要触达的恰恰是从不打开设置的用户。该图层本身可穿透点击，
 * 条目只在自己的卡片范围内接收指针事件。
 */
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from 'react'
import { FTSHARE_API_KEY_APPLY_URL, FTSHARE_API_KEY_REF, FTSHARE_CREDENTIAL_EVENTS, FREE_KEY_NOTICE_STORAGE_KEY } from '../api-key/contract.js'
import type { ApiKeyCardContext } from '../api-key/card.js'
import { createApiKeyClient } from '../api-key/client-api.js'
import { createSettingsTransport } from '../../core/client-transport.js'
import { browserNoticeStorage, readNoticeSeen, writeNoticeSeen, type NoticeFlagStorage } from './storage.js'
import { FREE_KEY_NOTICE_ID, FREE_KEY_NOTICE_SLOT, isViewIdle, shouldShowNotice, type FreeKeyNoticeSessionState } from './decision.js'
import { FREE_KEY_NOTICE_CSS } from './styles.js'

/** 停留时长：足够读完一句话并决定要不要去获取，又不至于一直挂在界面上。 */
export const FREE_KEY_NOTICE_AUTO_DISMISS_MS = 12_000

export { FREE_KEY_NOTICE_ID, FREE_KEY_NOTICE_SLOT }

/** 提示组件依赖的外部输入；全部可注入，测试不需要真实网络与浏览器存储。 */
export interface FreeKeyNoticeDeps {
  /** 读当前 Key 是否已配置；reject 表示读不到。 */
  readConfigured: () => Promise<boolean>
  /** 订阅「Key 可能变了」，配置好后立即收起。 */
  subscribeConfigured: (listener: () => void) => () => void
  storage: NoticeFlagStorage | undefined
  applyUrl: string
}

/**
 * 把异步的 `configured` 摊成 uSES 快照。只在有订阅者时读一次，订阅清理时停止。
 * @param deps - 读函数与订阅函数。
 * @returns uSES 快照源。
 */
function useConfigured(deps: FreeKeyNoticeDeps): boolean | undefined {
  const source = useMemo(() => {
    let value: boolean | undefined
    let stop: (() => void) | undefined
    const listeners = new Set<() => void>()
    const publish = () => { for (const listener of [...listeners]) listener() }
    const load = () => {
      deps.readConfigured().then(next => { value = next; publish() }, () => { /* 读失败保持 undefined */ })
    }
    return {
      getSnapshot: () => value,
      subscribe: (listener: () => void) => {
        listeners.add(listener)
        if (stop === undefined) {
          load()
          const off = deps.subscribeConfigured(load)
          stop = () => { off() }
        }
        return () => {
          listeners.delete(listener)
          if (listeners.size === 0) {
            stop?.()
            stop = undefined
          }
        }
      },
    }
  }, [deps])
  return useSyncExternalStore(source.subscribe, source.getSnapshot, source.getSnapshot)
}

/** 槽位提供的标准份额里，这里只用得到的这一个（由 ui-session 合并进所有槽位）。 */
type UseSessionsShare = (selector: (state: FreeKeyNoticeSessionState) => boolean) => boolean

/**
 * 提示本体。
 * @param props - 依赖注入，以及宿主通过槽位交给每个条目的标准份额。
 * @returns 左下角卡片，或 null。
 */
export function FreeKeyNotice({ deps, useSessions }: {
  deps: FreeKeyNoticeDeps
  useSessions: UseSessionsShare
}): ReactNode {
  const [seen, setSeen] = useState(() => readNoticeSeen(deps.storage, FREE_KEY_NOTICE_STORAGE_KEY))
  const [visible, setVisible] = useState(true)
  const configured = useConfigured(deps)
  const viewIdle = useSessions(isViewIdle)
  const show = visible && shouldShowNotice({ seen, configured, viewIdle })

  // 出现即记：自动消失或用户没点时也要落盘，不然下次启动又弹。
  useEffect(() => {
    if (!show || seen) return
    writeNoticeSeen(deps.storage, FREE_KEY_NOTICE_STORAGE_KEY)
    setSeen(true)
  }, [show, seen, deps.storage])

  // 自动淡出。悬停时暂停，移开后按剩余时间继续，避免用户正要看就被收走。
  const deadline = useRef<number | undefined>(undefined)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const dismiss = useCallback(() => { setVisible(false) }, [])
  const hold = useCallback(() => {
    if (timer.current !== undefined) clearTimeout(timer.current)
    timer.current = undefined
    deadline.current = undefined
  }, [])
  const resume = useCallback(() => {
    if (deadline.current === undefined) return
    const remaining = Math.max(0, deadline.current - Date.now())
    timer.current = setTimeout(dismiss, remaining)
  }, [dismiss])
  useEffect(() => {
    if (!show) return
    deadline.current = Date.now() + FREE_KEY_NOTICE_AUTO_DISMISS_MS
    timer.current = setTimeout(dismiss, FREE_KEY_NOTICE_AUTO_DISMISS_MS)
    return () => {
      if (timer.current !== undefined) clearTimeout(timer.current)
      timer.current = undefined
      deadline.current = undefined
    }
  }, [show, dismiss])

  if (!show) return null

  return <>
    <style>{FREE_KEY_NOTICE_CSS}</style>
    <aside
      className="ftshare-free-key-notice"
      role="status"
      aria-live="polite"
      onMouseEnter={hold}
      onMouseLeave={resume}
    >
      <div className="ftshare-free-key-head">
        <strong>免费获取 Key</strong>
        <button type="button" className="ftshare-free-key-close" aria-label="关闭" onClick={dismiss}>✕</button>
      </div>
      <p>海量金融数据，一次配置长期使用</p>
      <div className="ftshare-free-key-actions">
        <a className="primary" href={deps.applyUrl} target="_blank" rel="noreferrer" onClick={dismiss}>去获取</a>
        <button type="button" onClick={dismiss}>知道了</button>
      </div>
    </aside>
  </>
}

/**
 * 浏览器侧装配：把凭据通道、真实 localStorage 接到组件上。
 * `useSessions` 是宿主交给 `shell.overlay` 条目的标准份额，从 props 透传而不是自造。
 * @param ctx - 卡片那套上下文（slots + 凭据失效事件）。
 * @returns 槽位组件工厂。
 */
export function createFreeKeyNotice(ctx: ApiKeyCardContext): (props: { useSessions: UseSessionsShare }) => ReactNode {
  const api = createApiKeyClient(createSettingsTransport())
  const subscribeConfigured = (listener: () => void) => {
    const disposers = FTSHARE_CREDENTIAL_EVENTS.map(event => ctx.remote.$on(event, ref => { if (ref === FTSHARE_API_KEY_REF) listener() }))
    disposers.push(ctx.on('connection/reset', listener))
    return () => { for (const dispose of disposers) dispose() }
  }
  const deps: FreeKeyNoticeDeps = {
    readConfigured: async () => (await api.describe()).configured,
    subscribeConfigured,
    storage: browserNoticeStorage(),
    applyUrl: FTSHARE_API_KEY_APPLY_URL,
  }
  return ({ useSessions }) => <FreeKeyNotice deps={deps} useSessions={useSessions} />
}
