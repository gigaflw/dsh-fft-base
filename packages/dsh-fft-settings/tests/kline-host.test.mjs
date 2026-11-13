// 浏览器半在挂载时发布图表可选的宿主 chrome：FT bundle 依赖它，
// 让图表不画浮动 K、不弹首启/界面升级提示。
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

const requireCjs = createRequire(import.meta.url)

/** Enough of React for the bundle factories; the test only applies the plugin. */
const REACT = {
  createElement: () => null,
  useState: value => [typeof value === 'function' ? value() : value, () => {}],
  useEffect: () => {},
  useMemo: fn => fn(),
  useCallback: fn => fn,
  useRef: value => ({ current: value }),
  useSyncExternalStore: (_subscribe, get) => get(),
  Fragment: Symbol('Fragment'),
}
const JSX_RUNTIME = { jsx: () => null, jsxs: () => null, Fragment: Symbol('Fragment') }

/** Execute the browser bundle with a captured ModuleLoader call. */
function loadClient() {
  let captured
  globalThis.window = { __ModuleLoader__: { load: spec => { captured = spec } } }
  try {
    const bundle = requireCjs.resolve('../lib/client.js')
    delete requireCjs.cache[bundle]
    requireCjs(bundle)
  } finally {
    delete globalThis.window
  }
  assert.ok(captured, 'module loader was not called')
  return captured.factory(id => {
    if (id === 'react') return REACT
    if (id === 'react/jsx-runtime') return JSX_RUNTIME
    throw new Error(`unexpected require: ${id}`)
  })
}

/** The renderer context shape the client half touches, with `provide` recorded. */
function fakeContext() {
  const published = new Map()
  return {
    published,
    slots: { inject: () => () => {}, register: () => () => {} },
    remote: { $on: () => () => {} },
    on: () => () => {},
    inject: () => () => {},
    provide: (name, value) => { published.set(name, value) },
  }
}

test('publishes the kline host chrome once the client half applies', () => {
  const ctx = fakeContext()
  loadClient().apply(ctx)
  assert.deepEqual(ctx.published.get('klineHost'), { entry: 'tab', onboarding: 'off' })
})
