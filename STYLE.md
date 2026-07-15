# UI Style Guide

ArUcoGridGen should feel like a precise, compact engineering tool: quiet neutral surfaces, crisp geometry, dense but readable controls, and a single lime accent. The calibration board remains the visual focus; decoration is restrained.

## Theme and color

Use semantic CSS variables from `frontend/src/styles.css`; do not hard-code theme-dependent colors in components.

| Role | Light | Dark |
|---|---|---|
| App / workspace | `#f4f5f2` / `#f1f2ef` | `#101210` / `#0d0f0d` |
| Header / inspector | `#ffffff` / `#fafbfa` | `#151815` / `#121512` |
| Surface / hover | `#ffffff` / `#f7f8f5` | `#1b1f1b` / `#232823` |
| Selected surface | `#f5f8e7` | `#262d18` |
| Primary text | `#20241f` | `#f1f3ee` |
| Secondary / muted text | `#545b53` / `#656c63` | `#c2c8bf` / `#aab2a7` |
| Border / control border | `#dfe2dc` / `#ccd1c9` | `#353b34` / `#465045` |
| Accent | `#b1cb21` (hover `#a7c01e`) | same |
| Accent ink | `#252c05` | same |

The lime accent communicates the primary action, active selection, enabled switch, focus, and success/current state. Avoid using it as general decoration. Warnings use warm amber, errors muted red, and success uses olive-tinted surfaces. The printable preview is always white and must not invert in dark mode.

## Light/dark toggle

- Place a `34 × 34 px` outlined icon button in the header beside the GitHub link.
- Show a moon in light mode and a sun in dark mode; its accessible label describes the theme it will switch to.
- Use the system preference on first visit, save an explicit choice in `localStorage`, and set both `data-theme` and `color-scheme` on the root element.
- Swap the MATCH COW brand image for the theme-appropriate asset. Theme changes should recolor semantic tokens, not alter layout.

## Typography and iconography

- Use Inter with the system sans-serif stack as fallback.
- Keep the hierarchy compact: `17 px` app title, `16 px` section heading, `13 px` card heading, `11–12 px` controls, and `9–10 px` metadata and badges.
- Use medium-to-bold weights (`610–700`) for labels and headings; supporting copy is regular and muted.
- Use Lucide outline icons at roughly `14–18 px`. Icons should clarify actions, not decorate every label.

## Shape, spacing, and depth

- Use `10 px` radii for cards, `7–8 px` for controls and popovers, and pill/circle shapes only for badges, switches, and icon buttons.
- Use `1 px` neutral borders to define structure. Prefer border or background changes over large shadows.
- Keep spacing on a compact `4 px` rhythm: fields are usually `12 px` apart, card padding is `13–15 px`, and major regions use `20–26 px`.
- Shadows are subtle on cards, stronger only for the paper preview, popovers, and toasts.

## Layout

The desktop UI has a `68 px` header, a fixed `430 px` scrolling inspector on the left, and a flexible gray workspace on the right. The preview toolbar and paper are centered with a `1040 px` maximum width. Below `760 px`, stack the inspector above the workspace; below `520 px`, collapse the brand copy and GitHub label to icons.

## Components and interaction

- **Cards/accordions:** white or charcoal surfaces with thin borders; section titles stay visible and compact.
- **Inputs/selects:** `34 px` high, plain surfaces, `7 px` corners, stronger border on hover, lime focus ring on keyboard focus.
- **Buttons:** lime-filled primary, bordered secondary, and transparent ghost variants. Keep labels short and pair icons with important actions.
- **Selection:** use a lightly tinted surface plus lime border/ring; board cards also show a circular check mark.
- **Switches:** `34 × 19 px` pill track, neutral when off and lime when on, with a white `15 px` thumb.
- **Status:** small uppercase pill badges; current is olive, loading/stale amber, and errors red.
- **Feedback:** keep help text muted and close to its control; use inline error summaries for configuration problems and toasts for completed reversible actions.
- **Motion:** transitions are quick (`150–180 ms`) and functional. Respect `prefers-reduced-motion`.

Maintain visible keyboard focus, sufficient contrast in both themes, descriptive icon-button labels, and a minimum supported viewport width of `320 px`.
