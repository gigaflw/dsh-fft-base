/**
 * 一次性提示的样式：固定在左下角的非阻塞卡片。
 *
 * 不盖遮罩、不抢焦点——这一层（宿主的 `shell.overlay`）本身可穿透点击，
 * 条目只有在这张卡片范围内才接收指针事件，所以卡片以外的界面照常可用。
 * 位置用 `fixed` 而不是依赖外层布局：浮层是 `inset:0` 的绝对定位层，
 * 条目自己决定停在哪里。
 *
 * 颜色全走 `--dsw-alias-*` 与 `--ft-*` 变量，深色／浅色两套调色板共用一份。
 */
export const FREE_KEY_NOTICE_CSS = `
.ftshare-free-key-notice { position:fixed; left:24px; bottom:24px; z-index:20; box-sizing:border-box; width:min(320px, calc(100vw - 48px)); padding:16px; border:0.5px solid var(--dsw-alias-border-l2,rgba(0,0,0,.1)); border-radius:var(--dsw-radius-xl,20px); background:var(--dsw-alias-bg-layer-2,#fff); color:var(--dsw-alias-label-primary,#0f1115); box-shadow:var(--dsw-elevation-prominent,0 3px 8px rgba(0,0,0,.04), 0 0 20px rgba(0,0,0,.05)); animation:ftshareNoticeIn .2s ease; }
.ftshare-free-key-notice * { box-sizing:border-box; }
.ftshare-free-key-notice .ftshare-free-key-head { display:flex; align-items:flex-start; justify-content:space-between; gap:8px; }
.ftshare-free-key-notice strong { font-size:14px; font-weight:500; line-height:22px; }
.ftshare-free-key-notice .ftshare-free-key-close { flex:none; width:22px; height:22px; display:inline-flex; align-items:center; justify-content:center; border:none; border-radius:var(--dsw-radius-sm,8px); background:transparent; color:var(--dsw-alias-label-secondary,#61666b); font:inherit; font-size:12px; line-height:1; cursor:pointer; }
.ftshare-free-key-notice .ftshare-free-key-close:hover { background:var(--dsw-alias-bg-layer-3,#f9fafb); }
.ftshare-free-key-notice p { margin:6px 0 14px; font-size:13px; line-height:1.6; color:var(--dsw-alias-label-secondary,#61666b); }
.ftshare-free-key-notice .ftshare-free-key-actions { display:flex; gap:8px; }
.ftshare-free-key-notice .ftshare-free-key-actions :is(button,a) { min-height:30px; display:inline-flex; align-items:center; justify-content:center; border-radius:var(--dsw-radius-md,12px); border:0.5px solid var(--dsw-alias-border-l4,rgba(0,0,0,.16)); padding:0 12px; font:inherit; font-size:13px; background:transparent; color:inherit; text-decoration:none; cursor:pointer; }
/* 主入口用品牌黄的半透明底：保留 FT 的色，又不至于在左下角变成一块醒目的亮黄。
   文字仍取正文主色（不是压在上面的深黑字），70% 在深浅两套调色板下都能读。 */
.ftshare-free-key-notice .ftshare-free-key-actions .primary { flex:1; background:color-mix(in srgb,var(--ft-accent,#f0c433) 70%,transparent); border-color:var(--ft-accent,#f0c433); color:var(--dsw-alias-label-primary,#0f1115); font-weight:500; }
.ftshare-free-key-notice .ftshare-free-key-actions .primary:hover { background:color-mix(in srgb,var(--ft-accent,#f0c433) 82%,transparent); }
@keyframes ftshareNoticeIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
@media (prefers-reduced-motion: reduce) { .ftshare-free-key-notice { animation:none; } }
`
