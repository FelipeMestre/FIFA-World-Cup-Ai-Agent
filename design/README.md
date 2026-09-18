# World Cup AI Scout — design spec

App name: **World Cup AI Scout**. The design system it is built on is still called "Owl Analytics" (tokens.json); its colors and type are used as-is. The logo is a binoculars scout mark (blue #4E8EF7 on a white tile) and the assistant signs its replies as "Scout".

Source of truth: https://claude.ai/artifact/7p4YV7CYG1LnTQGcaGeKMD (design canvas).
This folder is a snapshot for implementation. Re-sync it when the canvas changes.

## Files

| Path | What it is |
|------|------------|
| `tokens.json` | Design tokens: colors, type scale, spacing, radius, shadow. Build the theme from this. |
| `canvas.json` | Artboard index: sizes, titles, notes. |
| `artboards/*.dc.html` | One screen or component per file. **Reference only** — a canvas-editor format (`<x-dc>`, `{{holes}}`, `<sc-for>`, `<dc-import>`), not runnable in Next.js. Read the inline styles for exact values and the `renderVals()` script for the sample data shape. |

## Artboard → implementation map

| Artboard | Build as |
|----------|----------|
| `Login` | `/login` route |
| `Main` | Chat page, empty state |
| `HomeActive` | Chat page, active thread (all four widgets inline) |
| `HomePanel` | Chat page with side panel open |
| `WidgetTeam` / `WidgetMatch` / `WidgetPlayer` / `WidgetCompare` | Compact chat widgets, 640px desktop, full width mobile |
| `PanelTeam` / `PanelMatch` / `PanelPlayer` / `PanelCompare` | Side-panel detail views, 480px |
| `MobileEmpty` / `MobileChat` / `MobileSheet` | Mobile layouts; panel becomes a full-height sheet |
| `AppSidebar` | Left-hand sidebar (264px): New chat, previous chats (click to resume), user name + settings at the bottom. Collapses to a 72px rail on the far left while the detail panel is open (layout: rail → chat → panel) |
| `Foundations` | Color and type rules |
| `Components` | Atoms: ChatBubble, WidgetFrame, StatChip, PanelHeader, ComparisonRow, TimelineItem, actions, ResultPill, ProfileTag |

## Rules that must survive implementation

- **Fonts**: Space Grotesk (headings), IBM Plex Sans (prose, labels), IBM Plex Mono (every measured number, tabular figures).
- **Violet `brand` #7E6FEE** only for the assistant (logo, avatar) and the one primary action (send, sign in).
- **Series colors**: side A / home / player A = `accent-live` #4E8EF7; side B / away / player B = `ink-secondary` #ABB4C4; benchmark = `data-neutral` #8B96AA tick marker.
- **Outcome colors never alone**: always with ▲ ▼ or W/D/L.
- **Surfaces**: page 950 → shells/panel 900 → widgets/tiles/assistant bubble 800 → hover 700 → selected 600. User bubble `chat-user-surface`.
- **Data limits**: no passing, distance, sprint or tracking metrics. Positions only GK/DEF/MID/FWD. Confirm player-level shots exist in the dataset.
- **Focus**: 2px `accent-live` outline, 2px offset. Touch targets ≥ 44px.
- All numbers in the artboards are illustrative placeholders, not real results.

## Premium layer (extends the tokens)

Applied to Login, Main, HomeActive, HomePanel, AppSidebar and the four widgets. Panels and mobile still use the flatter v1 style.

- Ambient glow: radial gradients of `brand` (≈16–22% alpha) at the top of screens, `accent-live` (≈10%) at a far corner.
- Cards: 16px radius, `border-subtle` outline, `inset 0 1px 0 rgba(244,246,249,0.06)` top highlight plus `shadow-md`.
- Widget headers: faint tint of the side-A color; stats in one divided strip instead of separate chips.
- Assistant replies: no bubble; scout signature row + source chip + copy/regenerate actions. User bubble keeps `chat-user-surface` with an asymmetric 18/18/4/18 radius.
- Primary buttons: `brand` fill with a soft violet glow shadow.
- Candidates to add as tokens: `radius-2xl: 16px`, glow and highlight shadows.

## Widget contract

The assistant returns structured parts; the frontend maps each to a component:

```ts
type MessagePart =
  | { type: "text"; content: string }
  | { type: "team_widget"; data: TeamSummary }
  | { type: "match_widget"; data: MatchSummary }
  | { type: "player_widget"; data: PlayerSummary }
  | { type: "compare_widget"; data: PlayerComparison };
```

"View full details" opens the matching panel with the same entity id. Validate payloads with a schema.

## Panel behavior

- One entity at a time; opening another replaces it. Source widget shows "Showing in panel".
- Stays open across follow-up turns; composer placeholder names the pinned entity.
- Collapse keeps the last entity one click away; close clears it.
- State: `{ openEntity: { type, id } | null, collapsed: boolean, sourceMessageId }`, kept outside the thread.
- Mobile: full-height sheet over a 72% scrim, grab handle + close, no collapse.
