# Wave 17 — Bitwarden Secrets Center + Page-Shell Migration

## Scope & Rationale

Wave 17 pursued two complementary goals:

1. **Bitwarden-first Secrets Center** — expose secrets-provider status to the Command Desk dashboard without ever transmitting secret *values* to the browser. The UI reads metadata only; `.env` remains a fallback.
2. **DeckPageShell migration** — migrate the remaining legacy pages (Models, Skills, Plugins, MCP, Channels) onto the shared `DeckPageShell` / design-system controls, eliminating scattered bespoke layouts and aligning them with the Env page introduced in Wave 16.

Both goals were identified during a routing/header audit (Wave 16 retro) that surfaced UX regressions and inconsistencies in how environment paths were displayed.

---

## Commits

| SHA | Title | Slice |
|---|---|---|
| `0513a41f6` | `feat(web): Wave 17 Secrets Center - Bitwarden-first provider on /env` | Slice 1 |
| `621474ef5` | `Fix routing and header audit regressions.` | Slice 2 |
| `f9e33782e` | `Refresh models and skills pages with deck shell UX.` | Slice 2 |
| `593ffcdda` | `Modernize plugins, MCP, and channels legacy pages.` | Slice 2 |

### Slice 1 — Secrets Center (`0513a41f6`)

- Added `GET /api/secrets/status` backend endpoint — returns provider metadata (enabled, configured, secret count) with **no secret values** in the payload.
- Added `DeckSecretProviderCard` React component displaying per-provider health badges.
- Added `EnvPage` mounted on `DeckPageShell`, replacing the old flat env page.
- `.env` file remains as a fallback provider if Bitwarden SM is unavailable.

### Slice 2 — Audit Fixes + Page-Shell Migration (`621474ef5`, `f9e33782e`, `593ffcdda`)

- **Routing fix**: reinstated `/keys` as a route alias (regression from Wave 16).
- **Header fix**: corrected MCP page title casing in `web/src/lib/resolve-page-title.ts`.
- **Channels fix**: normalized env-path display in `ChannelsPage` to be consistent with other pages.
- Migrated **Models**, **Skills**, **Plugins**, **MCP**, and **Channels** pages onto `DeckPageShell` with design-system form controls.

---

## Audit Findings

| Finding | Status |
|---|---|
| `/keys` route alias missing (regression) | **Fixed** — `621474ef5` |
| MCP title casing wrong in `resolve-page-title.ts` | **Fixed** — `621474ef5` |
| `ChannelsPage` env-path display inconsistent | **Fixed** — `621474ef5` |
| Legacy page layouts not using `DeckPageShell` | **Fixed** — `f9e33782e`, `593ffcdda` |
| Mobile 390 px layout claim (`.deck-content-shell` width) | **Deferred** — `.deck-content-shell` already sets `width: 100%`; physical device verification not performed |
| Kanban board overhaul | **Deferred** — out of Wave 17 scope |

---

## Validation & Review Outcomes

- **TypeScript typecheck**: green (no new type errors).
- **Lint**: green.
- **Vite production build**: completed successfully.
- **Security review** (Bugbot): no findings within Wave 17 file scope.
- **Bugbot code review**: clean within Wave 17 files; four pre-existing bugs flagged outside Wave 17 scope (see `docs/routing-guardrail-bugs.md`).

---

## Pull Request

PR #13 — `cursor/command-desk-wave17` → `cursor/command-desk-wave-next` on `CarlosRubilar94/command-desk`.

Status: **Open, not merged.**

---

## Known / Deferred

- **Mobile 390 px**: The claim that `DeckPageShell` handles 390 px correctly is unverified on a physical device. `.deck-content-shell` uses `width: 100%`, which is consistent with full-width mobile rendering, but no explicit responsive breakpoint test was run.
- **Kanban board overhaul**: Flagged as optional improvement; deferred to a future wave.
- **Routing/guardrail bugs**: Four pre-existing HIGH/MED severity bugs in `agent/smart_model_routing.py` and `agent/conversation_loop.py` are documented in `docs/routing-guardrail-bugs.md`. These are outside Wave 17 scope and require a dedicated fix wave.
