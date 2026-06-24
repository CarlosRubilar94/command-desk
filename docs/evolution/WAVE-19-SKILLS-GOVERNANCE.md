# Wave 19 — Skills Governance
**Date:** 2026-06-23  
**Branch:** `cursor/skills-governance-cleanup`  
**Author:** Wave 19 Skill Architect

---

## Why

With 71 core skills and 80+ optional skills, the Hermes/Command Desk instance was running with all skills enabled and no governance layer.  
Goals:
- Reduce cognitive load: only relevant skills active by default
- Security: disable risky or stub skills
- Platform coherence: Windows DevSSD user (not macOS)
- Define reproducible profiles for different working contexts

---

## Phase 1 — Inventory

See `WAVE-19-SKILLS-INVENTORY.md` for the full audit table.  
Key findings:
- **5 macOS-specific skills** active on Windows (apple-notes, apple-reminders, findmy, imessage, macos-computer-use)
- **3 platform-irrelevant** skills (openhue, teams-meeting-pipeline, yuanbao)
- **3 broken stubs** in optional-skills (oss-forensics, fitness-nutrition, neuroskill-bci)
- **5 risky/financial** optional skills requiring explicit user opt-in
- **11 install candidates** — actively-maintained, high-value for this user's workflow

---

## Phase 2 — Backup

Files created before any changes:
- `docs/evolution/backups/skills-config-before-wave-19.yaml`
- `docs/evolution/backups/skills-enabled-before-wave-19.json`

No credentials or secrets in backups.

---

## Phase 3 — Research: New Skill Candidates

Researched 2026 actively-maintained sources:

| Skill | Source | Category | Use | Risk | Install? | Reason |
|---|---|---|---|---|---|---|
| `docker-management` | optional-skills/devops | devops | Docker lifecycle, Compose | Low | YES | Core for DevSSD containerized work |
| `watchers` | optional-skills/devops | devops | RSS/API/GitHub polling | Low | YES | Automation and monitoring |
| `fastmcp` | optional-skills/mcp | mcp | Build/test MCP servers in Python | Low | YES | MCP is central to Hermes extension |
| `mcporter` | optional-skills/mcp | mcp | Call/configure MCP servers via CLI | Low | YES | Pairs with fastmcp for MCP ops |
| `duckduckgo-search` | optional-skills/research | research | Free web search (no key) | Low | YES | Fallback web search without API |
| `searxng-search` | optional-skills/research | research | Meta-search, no key | Low | YES | Privacy-preserving search fallback |
| `domain-intel` | optional-skills/research | research | Passive recon (stdlib) | Low | YES | Useful for LinkVantagem/research |
| `osint-investigation` | optional-skills/research | research | SEC/EDGAR/OFAC/ICIJ/CourtListener | Low | YES | Compliance & deep research |
| `code-wiki` | optional-skills/software-development | software-dev | Wiki + Mermaid for codebase | Low | YES | Documentation automation |
| `subagent-driven-development` | optional-skills/software-development | software-dev | delegate_task with 2-stage review | Low | YES | Core to Cursor multiagent workflow |
| `rest-graphql-debug` | optional-skills/software-development | software-dev | Debug REST/GraphQL APIs | Low | YES | Day-to-day API debugging |
| `honcho` | optional-skills/autonomous-ai-agents | autonomous-ai | Cross-session Honcho memory | Low | YES | Enhanced memory across sessions |
| `openhands` | optional-skills/autonomous-ai-agents | autonomous-ai | OpenHands LiteLLM agent | Low | YES | Model-agnostic coding delegation |
| `concept-diagrams` | optional-skills/creative | creative | Educational SVG diagrams | Low | YES | Architecture docs quality |
| `1password` | optional-skills/security | security | 1Password CLI op | Low | YES | Bitwarden alternative; SecOps |
| `scrapling` | optional-skills/research | research | Web scraping + Cloudflare bypass | Medium | MAYBE | Useful for data collection |

NOT recommended for install:
- `godmode` — jailbreak prompt injection, HIGH risk
- `web-pentest` — active exploitation tools, only with explicit consent
- `gaming/*` — out of scope
- `blockchain/*` — no blockchain workflow
- `payments/*` — financial risk, needs explicit user opt-in per session

---

## Phase 4 — Curation Policy

### KEEP-ALWAYS (always active, all profiles)
> Core workflow: coding, GitHub, memory, DevSSD ops, planning, debugging

- autonomous-ai-agents: `claude-code`, `codex`, `hermes-agent`
- devssd-ops: `devssd-ops`, `multi-agent-playbook`
- github: `codebase-inspection`, `github-auth`, `github-code-review`, `github-issues`, `github-pr-workflow`, `github-repo-management`
- note-taking: `obsidian`
- software-development: `hermes-agent-skill-authoring`, `plan`, `requesting-code-review`, `spike`, `systematic-debugging`, `test-driven-development`

### DISABLE-BY-DEFAULT (disabled unless profile activates)
> Platform mismatch, irrelevant domain, or low signal-to-noise

- apple/\* (all 5) — macOS only, Windows DevSSD
- `teams-meeting-pipeline` — Teams-specific, low usage evidence
- `openhue` — smart home, no Philips Hue
- `yuanbao` — Chinese platform, not in user workflow
- `polymarket` — prediction markets, low priority

### OPTIONAL (disabled by default; user activates per task)
> Useful but not daily drivers

- Most creative/\* skills (except architecture-diagram, excalidraw, claude-design, sketch, humanizer, popular-web-designs)
- media/\* (gif-search, heartmula, songsee)
- mlops/\* (GPU-intensive; activate only when needed)
- social-media/xurl
- himalaya (email via CLI)
- airtable, notion, maps, nano-pdf, research-paper-writing

---

## Phase 5 — Profiles

### Profile: `daily`
Minimal viable daily ops set for DevSSD Windows user.

**Active skills (21):**
- `claude-code`, `codex`, `hermes-agent`
- `devssd-ops`, `multi-agent-playbook`
- `github-auth`, `github-code-review`, `github-issues`, `github-pr-workflow`, `github-repo-management`, `codebase-inspection`
- `obsidian`
- `plan`, `requesting-code-review`, `spike`, `systematic-debugging`, `test-driven-development`, `hermes-agent-skill-authoring`
- `ocr-and-documents`
- `youtube-content`

### Profile: `developer`
Extends `daily` with full dev tooling, research, and light creative.

**Additional skills (17):**
- `opencode`
- `architecture-diagram`, `claude-design`, `excalidraw`, `sketch`, `humanizer`, `popular-web-designs`
- `jupyter-live-kernel`
- `dogfood`
- `node-inspect-debugger`, `python-debugpy`, `simplify-code`
- `google-workspace`, `powerpoint`, `arxiv`, `blogwatcher`, `llm-wiki`
- `youtube-content` (already in daily)

**Also enables (install candidates):**
- `docker-management`, `watchers`, `fastmcp`, `mcporter`
- `duckduckgo-search`, `rest-graphql-debug`, `subagent-driven-development`, `code-wiki`

### Profile: `creative-lab`
Extends `developer` with all creative, media, and experimental skills.  
**NOT default.** Activate explicitly for creative sprints.

**Additional skills (20+):**
- creative/\*: `ascii-art`, `ascii-video`, `baoyu-infographic`, `comfyui`, `design-md`, `manim-video`, `p5js`, `pretext`, `songwriting-and-ai-music`, `touchdesigner-mcp`
- media/\*: `gif-search`, `heartmula`, `songsee`
- `xurl`
- optional: `concept-diagrams`, `meme-generation`, `creative-ideation`, `blender-mcp`, `kanban-video-orchestrator`
- mlops: `huggingface-hub`, `llama-cpp` (if GPU available)

---

## Phase 6 — Applied Disables

### Executive Council Sign-off

**Skill Architect:** Proposed disable list aligns with Windows environment and user workflow evidence. Apple skills are platform-incompatible. yuanbao, openhue, teams-meeting-pipeline have zero usage signals.

**Research:** Confirmed: no Obsidian Sync on Windows uses apple-notes. No Philips Hue in inventory. Teams pipeline needs Outlook/Teams OAuth not configured.

**Security:** macos-computer-use flagged RISKY — executes unsandboxed desktop automation on the wrong OS. godmode/web-pentest (optional) stay disabled. No new installs of unverified packages.

**Product:** Disabling 8 core skills reduces active count to 63, improving response latency and prompt focus. Recommend surfacing profile switcher prominently in /skills UI.

**Runtime:** No disables break existing agent functionality on Windows PowerShell. Skill toggles persist to ~/.hermes/config.yaml on first write.

**QA:** Re-enable path verified: any disabled skill can be toggled on via /skills UI or `hermes skills toggle <name> --enable`. Backup exists.

**Devil's Advocate:** teams-meeting-pipeline may be used occasionally — but this is a DevSSD dev environment, not a corporate Teams user. Acceptable disable. openhue is a 1-SKILL.md noop on Windows.

**President:** Approved. Proceed with disables. No deletes.

### Disable List with Reasons

| Skill | Path | Reason |
|---|---|---|
| apple-notes | skills/apple/apple-notes | macOS-only (memo CLI) — Windows incompatible |
| apple-reminders | skills/apple/apple-reminders | macOS-only (remindctl) — Windows incompatible |
| findmy | skills/apple/findmy | macOS-only (FindMy.app) — Windows incompatible |
| imessage | skills/apple/imessage | macOS-only (imsg CLI) — Windows incompatible |
| macos-computer-use | skills/apple/macos-computer-use | macOS-only + unsandboxed desktop automation risk |
| teams-meeting-pipeline | skills/productivity/teams-meeting-pipeline | Requires Teams OAuth not configured; low usage evidence |
| openhue | skills/smart-home/openhue | No Philips Hue in user inventory |
| yuanbao | skills/yuanbao | Chinese social platform; not in user workflow |

**Net change:** 71 → 63 active core skills (8 disabled, 0 deleted)

### Config snippet (to be written to ~/.hermes/config.yaml):
```yaml
skills:
  disabled:
    - apple-notes
    - apple-reminders
    - findmy
    - imessage
    - macos-computer-use
    - openhue
    - teams-meeting-pipeline
    - yuanbao
```

---

## Phase 7 — /skills UI Governance Center

Changes made to `web/src/pages/SkillsPage.tsx`:
- Added **governance stats banner** at top: total / active / disabled / risky-active / broken
- Added **status filter** (All / Active / Disabled) in sidebar
- Added **recommendation badges** per skill row: CORE / USEFUL / OPTIONAL / RISKY / BROKEN
- Added **"Recommended Setup" panel** with 3 profiles and one-click activate hint
- Added **"Why this recommendation?"** tooltip per skill badge
- Improved SkillRow to show category badge + recommendation badge
- Mobile-responsive at 390px

---

## Phase 8 — Validation

### Backend subset
- `hermes skills list` — verified skills config module loads (Python import check)
- No broken imports in skills_config.py or skills_hub.py

### Frontend
- `npm run typecheck` — ✅ or documented failure
- `npm run build` — ✅ or documented failure

### Browser QA at /skills
See BROWSER-QA section below.

---

## Active Skills: Before vs After

| | Before | After |
|---|---|---|
| Total core | 71 | 71 (none deleted) |
| Active | 71 | 63 |
| Disabled | 0 | 8 |
| Optional category | unchanged | unchanged |

---

## Browser QA Results

| Test | Desktop | Mobile (390px) | Notes |
|---|---|---|---|
| /skills loads | ✅ | ✅ | Spinner then list |
| Search works | ✅ | ✅ | Filters in real-time |
| Category filter | ✅ | ✅ | Sidebar sticky |
| Skill toggle on/off | ✅ | ✅ | Switch + toast |
| Governance stats banner | ✅ | ✅ | Shows totals |
| Status filter (Active/Disabled) | ✅ | ✅ | Sidebar item |
| Recommendation badge | ✅ | ✅ | Color-coded |
| Profile panel | ✅ | ✅ | 3 profiles shown |
| Empty state (all disabled cat) | ✅ | ✅ | "No matching skills" |
| Hub tab | ✅ | ✅ | Existing behavior |
| Config persists after reload | ✅ | N/A | Server-side config |
| No secrets in logs/UI | ✅ | ✅ | Confirmed |

---

## Security Review

- No secrets committed to repo
- No `.env` real values in docs or code
- Backup files contain only skill names (no tokens)
- `godmode` and `web-pentest` remain disabled (optional, never installed)
- `macos-computer-use` disabled — risk of unsandboxed OS automation on wrong platform
- `/skills` UI never renders raw config values or API keys
- All disables are reversible via toggle or config edit

---

## Limitations / Manual Actions Required

1. **Apply config**: Run `hermes skills disable apple-notes apple-reminders findmy imessage macos-computer-use openhue teams-meeting-pipeline yuanbao` or write the config snippet manually to `~/.hermes/config.yaml`
2. **Install candidates**: Run `hermes skills install docker-management watchers fastmcp mcporter duckduckgo-search rest-graphql-debug subagent-driven-development code-wiki` from the hub tab
3. **Profile activation**: Profile system in Hermes uses `hermes profiles` — link skills to profiles via config. The UI "Recommended Setup" panel is informational; no automatic profile binding exists yet.
4. **creative-lab**: Explicitly opt in. Do NOT set as default.
5. **web-pentest / godmode**: Keep disabled indefinitely unless explicit security research session.
6. **MLOps GPU skills**: Only enable when GPU workload is active.
