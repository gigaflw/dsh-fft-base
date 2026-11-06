import type { ReactNode } from 'react'
import type { PropsRenderSlots, PropsRuntime, SlotCore, SlotMap } from '@deepseek-ai/dsh-client-ui-slots'
// Type-only: pulls the `settings.section` SlotMap entry into this program.
import type {} from '@deepseek-ai/dsh-client-ui-settings/client'
import { FTSHARE_SETTINGS_CARD_SLOT, FTSHARE_SETTINGS_ICON_SLOT, FTSHARE_SETTINGS_SECTION } from './contract.js'
import { SETTINGS_CSS } from './styles.js'

/** Section slot this seam contributes into; declared by the settings shell. */
const FTSHARE_SETTINGS_SECTION_NAME = 'settings.section' as const

declare module '@deepseek-ai/dsh-client-ui-slots' {
  interface SlotMap {
    /** One card inside the FTShare settings section; `order` sets its position. */
    'ftshare.settings.card': {
      kind: 'list'
      scope: 'root'
      owner: FtshareSettingsCardOwnerProps
    }
    /**
     * Nav-row icon, declared by the settings shell from 0.2.2 on. Typed
     * locally because the host package that declares it is not a dependency;
     * the borrow only shapes our own registration.
     */
    'settings.section.icon': {
      kind: 'list'
      scope: 'root'
      inline: true
      owner: FtshareSettingsIconOwnerProps
    }
  }
}
/** Owner share of a nav icon: the edge the host asks for and the selected state. */
export interface FtshareSettingsIconOwnerProps {
  /** Requested square edge in pixels. */
  size: number
  /** Whether this section is the selected nav row. */
  active: boolean
}
/** Owner share of a card: the section supplies no card-specific props. */
export interface FtshareSettingsCardOwnerProps {
  /** Marker field: card owner props are intentionally empty. */
  children?: never
}
/**
 * The slice of the renderer-owned slots service this seam uses.
 *
 * `register` IS the ui-slots registration signature (the runtime registry
 * reuses it verbatim, adding disposal through the caller's fiber); `inject`
 * is the runtime wrapper's declaration-lifetime hook, which is why it is
 * mirrored structurally here.
 */
export interface FtshareSettingsSlotsService {
  readonly register: SlotCore['register']
  /** Run `callback` for each declaration lifetime of `key`. */
  inject(key: keyof SlotMap & string, callback: () => () => void): () => void
}
/**
 * Browser context the section shell requires: the renderer's slots service.
 * A card that needs more (its own services, invalidation events) declares the
 * extra members on its own context type.
 */
export interface FtshareSettingsShellContext {
  slots: FtshareSettingsSlotsService
}
/** Composed props of the section entry: the shell's owner share plus its declared child render. */
export type FtshareSettingsSectionProps =
  & PropsRuntime<typeof FTSHARE_SETTINGS_SECTION_NAME>
  & PropsRenderSlots<typeof FTSHARE_SETTINGS_CARD_SLOT>

/**
 * The settings section shell: core CSS variables, the section chrome, and the
 * single render site every card appears at. Cards own everything inside it.
 */
export function FtshareSettingsSection({ renderSlot }: FtshareSettingsSectionProps): ReactNode {
  return <>
    <style>{SETTINGS_CSS}</style>
    {renderSlot(FTSHARE_SETTINGS_CARD_SLOT, {})}
  </>
}

/**
 * Declare the card slot and contribute the section that renders it.
 *
 * Declaring the child slot is what authorizes the render site; a card
 * registering through {@link FTSHARE_SETTINGS_CARD_SLOT} before this runs waits
 * for the declaration instead of failing.
 * @param ctx - client context carrying the renderer's slots service.
 * @returns idempotent disposer for the section and its declaration.
 */
export function registerSettingsSection(ctx: FtshareSettingsShellContext): () => void {
  const disposeSection = ctx.slots.inject(FTSHARE_SETTINGS_SECTION_NAME, () => ctx.slots.register(
    {
      name: FTSHARE_SETTINGS_SECTION_NAME,
      ...FTSHARE_SETTINGS_SECTION,
      children: { [FTSHARE_SETTINGS_CARD_SLOT]: { kind: 'list', scope: 'root' } },
    },
    FtshareSettingsSection,
  ))
  const disposeIcon = registerSettingsIcon(ctx)
  return () => {
    disposeIcon()
    disposeSection()
  }
}

/**
 * Give the section its own nav-row icon where the host offers the seat.
 *
 * 0.2.2 added `settings.section.icon` and kept the shell's built-in gear for
 * sections with no contribution. On an older host the slot is never declared,
 * so `inject` never runs its callback and the gear stays — registering in
 * place would instead throw, because a slot must be declared before use.
 * @param ctx - client context carrying the renderer's slots service.
 * @returns idempotent disposer for the icon contribution.
 */
export function registerSettingsIcon(ctx: FtshareSettingsShellContext): () => void {
  return ctx.slots.inject(FTSHARE_SETTINGS_ICON_SLOT, () => ctx.slots.register(
    { name: FTSHARE_SETTINGS_ICON_SLOT, id: FTSHARE_SETTINGS_SECTION.id },
    FtshareSettingsIcon,
  ))
}

/**
 * The badge outline, in the 16-unit viewBox the shell asks for.
 *
 * Two subpaths: the arch that carries the F/T counter, and the plinth with its
 * side pillars — the badge's own two disconnected pieces. Vertices are on the
 * pixel grid and inset so a 1.3px stroke lands inside the box like the host
 * glyphs do.
 */
/**
 * The FT badge, hand-set on the 16px pixel grid, as four connected runs.
 *
 * The outer frame, both legs below the frame's shoulders, and the counter
 * bridge; the two slots that make the mark are the gaps between them. The
 * corners are explicit arcs rather than `stroke-linejoin: round` — a join
 * radius is fixed at half the stroke width, so join-based corners cannot be
 * rounded by more than the stroke.
 *
 * Geometry is inset so the ink lands at roughly the 13 units the host's own
 * nav glyphs occupy: at full bleed the mark read larger than every neighbour.
 */
const FT_MARK_PATHS = [
  'M4.40 2.90 L4.40 2.90 A0.90 0.90 0 0 1 5.30 2.00 L10.70 2.00 A0.90 0.90 0 0 1 11.60 2.90 L11.60 6.00 L13.10 6.00 A0.90 0.90 0 0 1 14.00 6.90 L14.00 13.10 A0.90 0.90 0 0 1 13.10 14.00 L2.90 14.00 A0.90 0.90 0 0 1 2.00 13.10 L2.00 6.90 A0.90 0.90 0 0 1 2.90 6.00 L4.40 6.00 Z',
  'M4.40 6.00 L4.40 10.40',
  'M11.60 6.00 L11.60 10.40',
  'M4.40 10.00 L5.90 10.00 A0.90 0.90 0 0 0 6.80 9.10 L6.80 7.70 A0.90 0.90 0 0 1 7.70 6.80 L8.30 6.80 A0.90 0.90 0 0 1 9.20 7.70 L9.20 9.10 A0.90 0.90 0 0 0 10.10 10.00 L11.60 10.00',
].join(' ')

/**
 * The section's nav-row glyph.
 *
 * `currentColor` and the host's own 1.3 stroke, so the mark carries the same
 * weight as its neighbours instead of reading as a lighter or active row.
 */
export function FtshareSettingsIcon({ size }: FtshareSettingsIconOwnerProps): ReactNode {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
      style={{ flex: 'none' }}
    >
      <path d={FT_MARK_PATHS} stroke="currentColor" strokeWidth="1.3" />
    </svg>
  )
}
