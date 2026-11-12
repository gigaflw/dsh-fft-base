/**
 * 一次性提示的注册入口。
 *
 * 它和设置卡片走同一个 `ctx.slots`，但目标是框架级的 `shell.overlay`——
 * 宿主给「徽标、toast、状态条、对话框」这类全局浮层留的加法槽（`kind: list`,
 * `scope: root`），`ui-layout` 的 AppFrame 常驻渲染它，不依赖设置面板是否打开。
 *
 * 两条注册纪律来自宿主的槽位契约：
 * 1. `ctx.slots.inject(key, ...)` 等到槽位被声明再注册——启动早期 `shell.overlay`
 *    可能还不存在，直接 `register` 会抛。
 * 2. `id` 必须自己的。槽位按 id 去重，复用宿主的 id 会顶掉别人的浮层。
 */
import type { ReactNode } from 'react'
// Type-only: pulls `shell.overlay` 的 SlotMap 声明（含 `useSessions` 这类标准份额）进本程序。
import type {} from '@deepseek-ai/dsh-client-ui-layout/client'
import type { ApiKeyCardContext } from '../api-key/card.js'
import { createFreeKeyNotice, FREE_KEY_NOTICE_ID, FREE_KEY_NOTICE_SLOT } from './card.js'

/**
 * 注册一次性提示。
 * @param ctx - 客户端上下文，需带 `slots` 服务。
 * @returns 幂等 disposer。
 */
export function registerFreeKeyNotice(ctx: ApiKeyCardContext): () => void {
  const component = createFreeKeyNotice(ctx)
  return ctx.slots.inject(FREE_KEY_NOTICE_SLOT, () => ctx.slots.register(
    { name: FREE_KEY_NOTICE_SLOT, id: FREE_KEY_NOTICE_ID, order: 100 },
    component,
  ))
}
