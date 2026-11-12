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
export const inject = ['slots', 'remote']
export function apply(ctx: FtshareSettingsClientContext): void {
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
