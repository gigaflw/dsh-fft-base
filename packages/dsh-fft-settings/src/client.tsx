import { registerApiKeyCard, type ApiKeyCardContext } from './features/api-key/card.js'
import { registerFreeKeyNotice } from './features/free-key-notice/index.js'
import { registerLogsCard } from './features/logs/card.js'
import { registerSettingsSection } from './core/shell.js'
import { applyBrandTokens, type BrandThemeContext } from './brand.js'
export * from './core/shell.js'
export { FREE_KEY_NOTICE_ID, FREE_KEY_NOTICE_SLOT, isViewIdle, shouldShowNotice, type FreeKeyNoticeSessionState } from './features/free-key-notice/decision.js'
export { readNoticeSeen, writeNoticeSeen, type NoticeFlagStorage } from './features/free-key-notice/storage.js'
/** Browser context this plugin's own client half requires. */
export type FtshareSettingsClientContext = ApiKeyCardContext
/** Publishing a client service; the renderer context carries it, card fakes do not. */
interface HostServiceContext {
  provide(name: string, value: unknown): void
}

/**
 * The chrome the FT host asks the chart to run with.
 *
 * The bundle owns the chart entry (its own right column) and its first-run
 * experience, so the chart must not draw the floating classic launcher or its
 * onboarding dialogs. This is kline's optional `klineHost` host contract: a
 * standalone chart install has no provider and keeps every upstream default.
 */
const KLINE_HOST_OPTIONS = { entry: 'tab', onboarding: 'off' } as const

export const inject = ['slots', 'remote']
export function apply(ctx: FtshareSettingsClientContext): void {
  ;(ctx as unknown as HostServiceContext).provide('klineHost', KLINE_HOST_OPTIONS)
  registerFtshareSettings(ctx)
  // The declared context above names only the services the cards read; the
  // brand layer defers on `theme` through the full Cordis context, so this
  // plugin still loads on a host without the theme service.
  applyBrandTokens(ctx as unknown as BrandThemeContext)
}
/**
 * Contribute the settings section, its cards, and the frame-wide notice.
 *
 * The notice deliberately does not live in the settings page: it has to reach
 * users who never open settings, so it takes a seat in `shell.overlay`.
 */
export function registerFtshareSettings(ctx: FtshareSettingsClientContext): void {
  registerSettingsSection(ctx)
  registerApiKeyCard(ctx)
  registerLogsCard(ctx)
  registerFreeKeyNotice(ctx)
}
