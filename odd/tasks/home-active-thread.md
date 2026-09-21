# Home · active thread (HomeActive.dc.html)

## Objective

The home page owns the conversation. `canvas.json` lists `Main` (empty state),
`HomeActive` (active thread) and `HomePanel` (side panel open) as three states
of **one** page, not three pages. Implement the active-thread state in
`HomeShell` and remove the separate `/chat` route.

## Problem / why

`/chat` was introduced earlier in this session on the mistaken assumption that
the chat was a distinct page with its own design. It is not. The composer
currently navigates to `/chat?prompt=…`; it should submit in place.

## Scope

In scope: active-thread rendering, thread header, sticky composer, in-place
submit, side-panel carry-over, deleting `/chat` + `ChatShell`.
Out of scope: backend changes, new widget types, history persistence.

## Constraints

- Design source of truth: `design/artboards/HomeActive.dc.html`.
- Reuse existing widgets/panels; do not re-author them.
- Do not fabricate content the data model lacks (provenance pill, follow-up
  suggestions) — omit and flag instead.

## Tasks

- [x] T1 Turn grouping + assistant/user turn components to design spec
- [x] T2 `HomeThread` list (36px between turns, 20px within, 14px in answer)
- [x] T3 Thread header (title + answers pill + Share) replacing status pill
- [x] T4 Sticky composer with fade, @Mention pill, submit in place
- [x] T5 `HomeShell` owns `useChatThread` + `useChatPanel`; empty vs active
- [x] T6 Delete `/chat` page, `ChatShell`, and its proxy matcher entry
- [x] T7 Verify: typecheck, lint, browser at desktop + mobile

## Acceptance

- Submitting from the empty state transitions to the thread in place, no route
  change.
- `/chat` 404s; no dead imports remain.
- Desktop matches HomeActive; mobile still renders.

## Checks

`npx tsc --noEmit`, `npm run lint`, browser verification (no test runner
configured for these components; TDD mode not enabled in this session).

## Progress

All tasks complete; uncommitted.

Verified: `npx tsc --noEmit` clean, `npm run lint` clean. In the browser at
1200x820, submitting from the empty state swapped to the thread in place with
no route change (URL stayed `/home`); thread header, user bubble, Scout
attribution and sticky follow-up composer all render. Mobile (375x812) renders
the same thread with the mobile top bar and no page scroll. The answer shows
"temporarily unavailable" because no backend is running in this environment --
the request went through the normal streaming path.

Also removed the global desktop top bar: no artboard has one (branding lives
in the sidebar, the content column owns its header). `AppHeader` is now
mobile-only, which the mobile artboards do specify.

Deliberately not built, for lack of backing data rather than oversight:
- provenance pill on answers ("7 matches") -- no such field on `ChatMessage`
- follow-up suggestion line under each answer -- same
- Share button is presentational; no share/permalink backend exists

Extracted `home-sidebar.tsx` (206 lines) out of `home-shell.tsx` to stay under
the 400-line standard; `home-shell.tsx` is now 308 lines.
