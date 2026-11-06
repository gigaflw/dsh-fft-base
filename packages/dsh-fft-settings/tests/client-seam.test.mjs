// 浏览器侧的缝：槽位 `ftshare.settings.card`。
//
// 这里用真实的 SlotCore 承担声明与登记（子槽位声明、按 id 去重、按 order
// 排序都是它的语义），只在它之上补两件运行时的东西：渲染器才有的
// `inject`（声明存在时同步执行、否则等声明）与列表投影 `renderSlot`
// （就是渲染器读 `entriesOfSlot` 的那一步）。因此本文件测的是本插件贡献
// 的注册与渲染位置，而不是自造的注册表。

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { SlotCore } from '@deepseek-ai/dsh-client-ui-slots'
import { registerSettingsSection } from '../lib/core/shell.js'
import { registerApiKeyCard } from '../lib/features/api-key/card.js'
import { registerLogsCard } from '../lib/features/logs/card.js'
import { FTSHARE_API_KEY_APPLY_URL, FTSHARE_API_KEY_REF, FTSHARE_SETTINGS_CARD_SLOT, FTSHARE_SETTINGS_ICON_SLOT, FTSHARE_SETTINGS_SECTION, LOGS_CARD_ID, LOGS_CARD_ORDER } from '../lib/contract.js'

/** Renderer-shaped slots service over a real SlotCore. */
function createSlots() {
  const core = new SlotCore()
  return {
    register: core.register.bind(core),
    /** Declaration-lifetime hook: run now when declared, otherwise on declaration. */
    inject(key, callback) {
      let dispose
      const activate = () => {
        if (dispose !== undefined || core.spec(key) === undefined) return
        dispose = callback() ?? (() => {})
      }
      const off = core.subscribeDeclaration(key, activate)
      activate()
      return () => { off(); const running = dispose; dispose = undefined; running?.() }
    },
    /** The list dispatch the renderer performs: every winning entry, in order. */
    renderSlot: (key, owner) => core.entriesOfSlot(key).map(entry => entry.component(owner)),
    core,
  }
}

/** The settings shell declares its section slot; nothing may register before that. */
function declareSettingsShell(slots) {
  return slots.register({ name: 'root', children: { 'settings.section': { kind: 'list', scope: 'root' } } }, () => 'shell')
}

/**
 * The 0.2.2 shell, which additionally declares the nav-icon seat. 0.2.1
 * declares only the section, so the same fixture with this helper left
 * uncalled models an older host.
 */
function declareSettingsShellWithIcon(slots) {
  return slots.register({
    name: 'root',
    children: {
      'settings.section': { kind: 'list', scope: 'root' },
      [FTSHARE_SETTINGS_ICON_SLOT]: { kind: 'list', scope: 'root', inline: true },
    },
  }, () => 'shell')
}

/** A client context with the invalidation surfaces the built-in card binds. */
function createContext(slots) {
  const subscriptions = []
  return {
    slots,
    subscriptions,
    remote: { $on: (event, listener) => { subscriptions.push([event, listener]); return () => {} } },
    on: (event, listener) => { subscriptions.push([event, listener]); return () => {} },
  }
}

test('the section declares the card slot and renders cards registered through it', async () => {
  const slots = createSlots()
  declareSettingsShell(slots)
  const ctx = createContext(slots)

  // The child slot does not exist until the section declares it, so a direct
  // registration before that is a load-time error, exactly as the framework
  // reports it.
  assert.throws(() => slots.register({ name: FTSHARE_SETTINGS_CARD_SLOT, id: 'too-early' }, () => 'too-early'), /is not declared/)

  const disposeSection = registerSettingsSection(ctx)
  const section = slots.core.entriesOfSlot('settings.section')
  assert.equal(section.length, 1)
  assert.deepEqual(section[0].options, { id: FTSHARE_SETTINGS_SECTION.id, order: FTSHARE_SETTINGS_SECTION.order, label: FTSHARE_SETTINGS_SECTION.label })
  // Declaring the child slot is what authorizes the section's render site.
  assert.deepEqual(section[0].children, { [FTSHARE_SETTINGS_CARD_SLOT]: { kind: 'list', scope: 'root' } })
  assert.deepEqual(slots.core.spec(FTSHARE_SETTINGS_CARD_SLOT), { kind: 'list', scope: 'root' })

  // The section's own component is the single render site for every card.
  assert.deepEqual(slots.renderSlot(FTSHARE_SETTINGS_CARD_SLOT, {}), [])
  slots.register({ name: FTSHARE_SETTINGS_CARD_SLOT, id: 'cockpit', order: 40, label: '投研舱' }, () => 'cockpit-card')

  const tree = section[0].component({ renderSlot: slots.renderSlot })
  const [, cards] = tree.props.children
  assert.deepEqual(cards, ['cockpit-card'])
  // The shell renders its own CSS in front of the cards.
  assert.match(tree.props.children[0].props.children, /--ftshare-text/)

  disposeSection()
  assert.equal(slots.core.spec(FTSHARE_SETTINGS_CARD_SLOT), undefined)
})

test('a card that registers before the section waits for the declaration and then renders', async () => {
  const slots = createSlots()
  declareSettingsShell(slots)
  const ctx = createContext(slots)
  let disposeCard
  // `settings.section` exists, but its child slot is declared by the section
  // entry the built-in client contributes; until then the card only waits.
  assert.doesNotThrow(() => { disposeCard = registerApiKeyCard(ctx) })
  assert.deepEqual(slots.core.entries(FTSHARE_SETTINGS_CARD_SLOT), [])

  const disposeSection = registerSettingsSection(ctx)
  const entries = slots.core.entriesOfSlot(FTSHARE_SETTINGS_CARD_SLOT)
  assert.equal(entries.length, 1)
  assert.deepEqual(entries[0].options, { id: 'apiKey', order: 10 })
  assert.equal(slots.renderSlot(FTSHARE_SETTINGS_CARD_SLOT, {}).length, 1)

  disposeCard()
  assert.deepEqual(slots.core.entries(FTSHARE_SETTINGS_CARD_SLOT), [])
  disposeSection()
})

test('the built-in card registers late, sorts by order and keeps its invalidation wiring', async () => {
  const slots = createSlots()
  declareSettingsShell(slots)
  const ctx = createContext(slots)
  const disposeSection = registerSettingsSection(ctx)

  // The built-in card arrives after the declaration, exactly like any other.
  const disposeCard = registerApiKeyCard(ctx)
  slots.register({ name: FTSHARE_SETTINGS_CARD_SLOT, id: 'cockpit', order: 40, label: '投研舱' }, () => 'cockpit-card')
  slots.register({ name: FTSHARE_SETTINGS_CARD_SLOT, id: 'no-order' }, () => 'no-order-card')

  const entries = slots.core.entriesOfSlot(FTSHARE_SETTINGS_CARD_SLOT)
  // The ledger sorts list entries by ascending `order`, and the ui-slots
  // runtime reads a missing `order` as 0 — so a card that omits `order` lands
  // in front of the built-in one (order 10) and an explicit order is the only
  // way to place a card after it.
  assert.deepEqual(entries.map(entry => entry.options.id), ['no-order', 'apiKey', 'cockpit'])
  assert.deepEqual(entries[1].options, { id: 'apiKey', order: 10 })

  // No priority is published: the built-in card only declares id/order, so a
  // second card claiming the same id at the same priority is a load-time error.
  assert.throws(() => slots.register({ name: FTSHARE_SETTINGS_CARD_SLOT, id: 'apiKey' }, () => null), /already has an entry with id "apiKey"/)

  const [, card] = slots.renderSlot(FTSHARE_SETTINGS_CARD_SLOT, {})
  assert.equal(typeof card.props.api.describe, 'function')
  let notified = 0
  const off = card.props.subscribeChanges(() => { notified++ })
  assert.deepEqual(ctx.subscriptions.map(([event]) => event), ['credentials/reference-updated', 'connection/reset'])
  const [[, credentialListener], [, resetListener]] = ctx.subscriptions
  credentialListener('ANOTHER_KEY')
  assert.equal(notified, 0, 'another credential reference never invalidates this card')
  credentialListener(FTSHARE_API_KEY_REF)
  resetListener()
  assert.equal(notified, 2)
  off()

  disposeCard()
  assert.deepEqual(slots.renderSlot(FTSHARE_SETTINGS_CARD_SLOT, {}), ['no-order-card', 'cockpit-card'])
  disposeSection()
})

test('both built-in cards register through the same slot and sort by ascending order', async () => {
  const slots = createSlots()
  declareSettingsShell(slots)
  const ctx = createContext(slots)

  // Both built-in cards may arrive before the section declares the child slot.
  const disposeLogs = registerLogsCard(ctx)
  const disposeApiKey = registerApiKeyCard(ctx)
  assert.deepEqual(slots.core.entries(FTSHARE_SETTINGS_CARD_SLOT), [])

  const disposeSection = registerSettingsSection(ctx)
  const entries = slots.core.entriesOfSlot(FTSHARE_SETTINGS_CARD_SLOT)
  assert.deepEqual(entries.map(entry => entry.options.id), ['apiKey', LOGS_CARD_ID])
  assert.deepEqual(entries.map(entry => entry.options.order), [10, LOGS_CARD_ORDER])
  assert.deepEqual(entries[1].options, { id: 'logs', order: 20 })
  // Both are ordinary list entries: no priority and no privileged options.
  assert.equal(entries.every(entry => entry.options.label === undefined), true)
  assert.equal(slots.renderSlot(FTSHARE_SETTINGS_CARD_SLOT, {}).length, 2)

  disposeLogs()
  assert.deepEqual(slots.core.entriesOfSlot(FTSHARE_SETTINGS_CARD_SLOT).map(entry => entry.options.id), ['apiKey'])
  disposeApiKey()
  disposeSection()
})

test('the API Key apply link carries the dsh-fft attribution and lives in one constant', async () => {
  const url = new URL(FTSHARE_API_KEY_APPLY_URL)
  assert.equal(url.origin + url.pathname, 'https://ftai.chat/me/profile')
  assert.equal(url.searchParams.get('tab'), 'api-key')
  // The site attributes the referrer from this pair; losing it silently breaks
  // the funnel, so it is pinned here rather than left to the page URL.
  assert.equal(url.searchParams.get('utm_source'), 'dsh-fft')

  // The card must reach the address through the constant: a second literal URL
  // is how the attribution drifts apart from the settings page.
  const source = await readFile(new URL('../src/features/api-key/card.tsx', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /ftai\.chat/)
  assert.match(source, /href=\{FTSHARE_API_KEY_APPLY_URL\}/)
})

test('the section claims the nav-icon seat when the host declares it', async () => {
  const slots = createSlots()
  declareSettingsShellWithIcon(slots)
  const ctx = createContext(slots)

  const dispose = registerSettingsSection(ctx)
  // The id must equal the section's own, or the shell filters the icon out.
  const icons = slots.core.entriesOfSlot(FTSHARE_SETTINGS_ICON_SLOT)
  assert.equal(icons.length, 1)
  assert.deepEqual(icons[0].options, { id: FTSHARE_SETTINGS_SECTION.id })

  // The glyph takes the edge the shell asks for and inherits the row text,
  // like every other nav glyph — it has no colour of its own.
  const glyph = icons[0].component({ size: 16, active: false })
  assert.equal(glyph.props.width, 16)
  assert.equal(glyph.props.height, 16)
  assert.equal(glyph.props.viewBox, '0 0 16 16')
  assert.equal(glyph.props.fill, 'none')
  assert.deepEqual(glyph.props.style, { flex: 'none' })
  const mark = glyph.props.children
  assert.equal(mark.props.stroke, 'currentColor')
  // The host's own stroke weight, so the mark does not read as a lighter row.
  assert.equal(mark.props.strokeWidth, '1.3')
  // Corners are explicit arcs: a `stroke-linejoin: round` radius is capped at
  // half the stroke, so joins alone cannot round them further than this.
  assert.equal(mark.props.strokeLinejoin, undefined)
  const d = mark.props.d
  assert.equal(d.match(/M/g).length, 4, 'outer frame, both legs, and the counter bridge')
  assert.equal(d.match(/Z/g).length, 1, 'only the outer frame closes')
  assert.ok(d.match(/A[\d.]+ [\d.]+ 0 0 [01]/g).length >= 8, 'corners must be arc-rounded')
  // Square caps only: a round cap on an open run would turn its end into a pill.
  assert.equal(mark.props.strokeLinecap, undefined)
  // The ink must stay inside the 16 unit box at this stroke weight.
  for (const [, x, y] of d.matchAll(/(?:[ML]|A[\d.]+ [\d.]+ 0 0 [01] )([\d.]+) ([\d.]+)/g)) {
    assert.ok(Number(x) >= 0.65 && Number(x) <= 15.35, `x ${x} leaves the 1.3 stroke's half-width`)
    assert.ok(Number(y) >= 0.65 && Number(y) <= 15.35, `y ${y} leaves the 1.3 stroke's half-width`)
  }

  dispose()
  assert.deepEqual(slots.core.entriesOfSlot(FTSHARE_SETTINGS_ICON_SLOT), [])
})

test('a host without the nav-icon seat keeps its built-in gear', async () => {
  // 0.2.1 declares only the section. Registering into the absent seat would
  // throw, so the contribution has to stay pending instead.
  const slots = createSlots()
  declareSettingsShell(slots)
  const ctx = createContext(slots)

  const dispose = registerSettingsSection(ctx)
  assert.deepEqual(slots.core.entriesOfSlot(FTSHARE_SETTINGS_ICON_SLOT), [])
  assert.deepEqual(slots.core.entriesOfSlot('settings.section').map(entry => entry.options.id), [FTSHARE_SETTINGS_SECTION.id])

  dispose()
  assert.deepEqual(slots.core.entriesOfSlot('settings.section'), [])
})

test('the section label follows the active locale', async () => {
  // A thunk is re-read per render; a plain string would freeze the language
  // that was active at registration, and a thunk closing over a value read
  // once at module load would still pin it. Only a per-call read follows a
  // language change without a plugin reload.
  assert.equal(typeof FTSHARE_SETTINGS_SECTION.label, 'function')
  const original = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  const pick = language => {
    Object.defineProperty(globalThis, 'navigator', { value: { language }, configurable: true })
    return FTSHARE_SETTINGS_SECTION.label()
  }
  try {
    assert.equal(pick('zh-CN'), '金融终端')
    assert.equal(pick('en-US'), 'FT Terminal')
    assert.equal(pick('zh-CN'), '金融终端')
  } finally {
    if (original === undefined) delete globalThis.navigator
    else Object.defineProperty(globalThis, 'navigator', original)
  }
})
