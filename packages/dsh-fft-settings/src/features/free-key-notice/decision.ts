/**
 * 「这条一次性提示该不该弹」的判定。
 *
 * 与渲染分开：判定是纯函数、零依赖，能在 Node 测试里直接钉住；渲染层只管把
 * 模态框摆出去。三条输入里任何一条没准备好都按「不弹」处理——这是刻意的，
 * 一次没弹只是少一次提醒，弹错一次就是打扰。
 */

/** 宿主 `shell.overlay` 槽名；这个 feature 只往这一个座位贡献。 */
export const FREE_KEY_NOTICE_SLOT = 'shell.overlay' as const
/** 条目 id：必须自己的，占用宿主的会顶掉别人的浮层。 */
export const FREE_KEY_NOTICE_ID = 'ftshare.free-key-notice' as const

/** 提示出现前需要的会话事实，只取用得到的字段。 */
export interface FreeKeyNoticeSessionState {
  phase: string
  byId: Record<string, { blank: boolean; retainedBy?: { mainView?: number } }>
}

/**
 * 主视图是否停在一个空会话上（没有内容会被弹窗挡住）。
 * @param state - 会话列表快照。
 * @returns 是否可以安全地弹出模态框。
 */
export function isViewIdle(state: FreeKeyNoticeSessionState): boolean {
  if (state.phase !== 'ready') return false
  const main = Object.values(state.byId).find(session => (session.retainedBy?.mainView ?? 0) > 0)
  return main === undefined || main.blank
}

/**
 * 是否应当显示提示。
 * - 已看过：不弹（设备级一次）；
 * - Key 已配置、或状态还读不到：不弹（读不到时宁可少弹）；
 * - 主视图被有内容的会话占着：不弹，等它空下来。
 * @param facts - 三个输入。
 * @returns 是否显示。
 */
export function shouldShowNotice(facts: {
  seen: boolean
  configured: boolean | undefined
  viewIdle: boolean
}): boolean {
  if (facts.seen) return false
  if (facts.configured !== false) return false
  return facts.viewIdle
}
