# Wave 19 — Skills Inventory
**Date:** 2026-06-23  
**Branch:** `cursor/skills-governance-cleanup`  
**Auditor:** Skill Architect (Wave 19)  
**Total core skills:** 71  **Total optional categories:** 20+

---

## Legend

| Tag | Meaning |
|---|---|
| KEEP-CORE | Essential for user's daily/dev workflow — always enabled |
| KEEP-USEFUL | Genuinely useful, lower priority — enable in `developer` profile |
| DISABLE-UNUSED | No evidence of use; macOS/platform mismatch or irrelevant domain |
| DISABLE-RISKY | Security/privacy risk or contains unsandboxed execution |
| REVIEW-MANUAL | One-time use or needs user validation before enabling |
| OPTIONAL | Creative or niche — only in `creative-lab` profile |
| INSTALL-CANDIDATE | Not yet installed; recommended external addition |
| BROKEN | SKILL.md empty/stub or depends on unavailable platform tool |
| DUPLICATE | Functionality covered by another KEEP-CORE skill |

---

## Core Skills Audit Table

| Skill | Category | Active? | Origin | Description | Deps | Risk | Recommendation |
|---|---|---|---|---|---|---|---|
| apple-notes | apple | Yes | builtin | Manage Apple Notes via memo CLI | macOS only | Platform mismatch | DISABLE-UNUSED |
| apple-reminders | apple | Yes | builtin | Apple Reminders via remindctl | macOS only | Platform mismatch | DISABLE-UNUSED |
| findmy | apple | Yes | builtin | Track Apple devices/AirTags via FindMy.app | macOS only | Platform mismatch | DISABLE-UNUSED |
| imessage | apple | Yes | builtin | Send/receive iMessages via imsg CLI | macOS only | Platform mismatch | DISABLE-UNUSED |
| macos-computer-use | apple | Yes | builtin | macOS desktop automation via computer-use | macOS only | Platform mismatch + RISKY | DISABLE-RISKY |
| claude-code | autonomous-ai-agents | Yes | builtin | Delegate coding to Claude Code CLI | claude CLI | Low | KEEP-CORE |
| codex | autonomous-ai-agents | Yes | builtin | Delegate coding to OpenAI Codex CLI | OpenAI key | Low | KEEP-CORE |
| hermes-agent | autonomous-ai-agents | Yes | builtin | Configure/extend Hermes Agent itself | None | Low | KEEP-CORE |
| opencode | autonomous-ai-agents | Yes | builtin | Delegate coding to OpenCode CLI | opencode CLI | Low | KEEP-USEFUL |
| architecture-diagram | creative | Yes | builtin | Dark SVG arch/cloud/infra diagrams | Python/browser | Low | KEEP-USEFUL |
| ascii-art | creative | Yes | builtin | ASCII art via pyfiglet, cowsay, image-to-ascii | Python | Low | OPTIONAL |
| ascii-video | creative | Yes | builtin | Convert video to ASCII animation | ffmpeg | Low | OPTIONAL |
| baoyu-infographic | creative | Yes | builtin | 21-layout infographics | browser | Low | OPTIONAL |
| claude-design | creative | Yes | builtin | One-off HTML artifacts (landing, deck) | browser | Low | KEEP-USEFUL |
| comfyui | creative | Yes | builtin | Images/video/audio with ComfyUI | ComfyUI server | Medium (external server) | OPTIONAL |
| design-md | creative | Yes | builtin | Author/validate Google DESIGN.md tokens | None | Low | OPTIONAL |
| excalidraw | creative | Yes | builtin | Hand-drawn Excalidraw JSON diagrams | browser | Low | KEEP-USEFUL |
| humanizer | creative | Yes | builtin | Humanize text (strip AI-isms) | None | Low | KEEP-USEFUL |
| manim-video | creative | Yes | builtin | Manim math/algo video animations | manim | Low | OPTIONAL |
| p5js | creative | Yes | builtin | p5.js generative art/shaders | browser | Low | OPTIONAL |
| popular-web-designs | creative | Yes | builtin | 54 real design systems reference | browser | Low | KEEP-USEFUL |
| pretext | creative | Yes | builtin | Creative browser demos (pretext) | browser | Low | OPTIONAL |
| sketch | creative | Yes | builtin | Throwaway HTML mockups (2-3 variants) | browser | Low | KEEP-USEFUL |
| songwriting-and-ai-music | creative | Yes | builtin | Songwriting + Suno AI music prompts | Suno API | Low | OPTIONAL |
| touchdesigner-mcp | creative | Yes | builtin | Control TouchDesigner via MCP | TouchDesigner | Low | OPTIONAL |
| jupyter-live-kernel | data-science | Yes | builtin | Iterative Python via live Jupyter kernel | jupyter | Low | KEEP-USEFUL |
| devssd-ops | devssd-ops | Yes | custom | DevSSD operational context + Obsidian memory | None | Low | KEEP-CORE |
| multi-agent-playbook | devssd-ops | Yes | custom | Multi-agent playbooks for DevSSD/Cursor | None | Low | KEEP-CORE |
| dogfood | dogfood | Yes | builtin | Exploratory QA of web apps | browser | Low | KEEP-USEFUL |
| himalaya | email | Yes | builtin | Himalaya CLI IMAP/SMTP email | himalaya CLI | Medium (email creds) | OPTIONAL |
| codebase-inspection | github | Yes | builtin | Inspect codebases with pygount | pygount | Low | KEEP-CORE |
| github-auth | github | Yes | builtin | GitHub auth setup (HTTPS, SSH, gh) | gh CLI | Low | KEEP-CORE |
| github-code-review | github | Yes | builtin | Review PRs via gh or REST | gh CLI | Low | KEEP-CORE |
| github-issues | github | Yes | builtin | Create/triage GitHub issues | gh CLI | Low | KEEP-CORE |
| github-pr-workflow | github | Yes | builtin | GitHub PR lifecycle | gh CLI | Low | KEEP-CORE |
| github-repo-management | github | Yes | builtin | Clone/create/fork repos, manage releases | gh CLI | Low | KEEP-CORE |
| gif-search | media | Yes | builtin | Search/download GIFs from Tenor | curl/jq | Low | OPTIONAL |
| heartmula | media | Yes | builtin | HeartMuLa song generation | External API | Low | OPTIONAL |
| songsee | media | Yes | builtin | Audio spectrograms/features | Python audio | Low | OPTIONAL |
| youtube-content | media | Yes | builtin | YouTube transcripts to summaries/threads | yt-dlp | Low | KEEP-USEFUL |
| evaluating-llms-harness | mlops/evaluation | Yes | builtin | lm-eval-harness LLM benchmarking | Python | Medium | OPTIONAL |
| weights-and-biases | mlops/evaluation | Yes | builtin | W&B experiment tracking | W&B API key | Low | OPTIONAL |
| huggingface-hub | mlops | Yes | builtin | HuggingFace hf CLI | HF token | Low | KEEP-USEFUL |
| llama-cpp | mlops/inference | Yes | builtin | llama.cpp local GGUF inference | llama.cpp | Medium (local GPU) | OPTIONAL |
| serving-llms-vllm | mlops/inference | Yes | builtin | vLLM high-throughput serving | GPU required | Medium | OPTIONAL |
| audiocraft | mlops/models | Yes | builtin | AudioCraft MusicGen/AudioGen | GPU required | Medium | OPTIONAL |
| segment-anything | mlops/models | Yes | builtin | SAM zero-shot image segmentation | GPU required | Medium | OPTIONAL |
| obsidian | note-taking | Yes | builtin | Read/search/create Obsidian notes | Obsidian vault | Low | KEEP-CORE |
| airtable | productivity | Yes | builtin | Airtable REST API | Airtable key | Low | OPTIONAL |
| google-workspace | productivity | Yes | builtin | Gmail, Calendar, Drive, Docs, Sheets | gws CLI / OAuth | Medium (OAuth) | KEEP-USEFUL |
| maps | productivity | Yes | builtin | Geocode, POIs, routes via OpenStreetMap | None | Low | OPTIONAL |
| nano-pdf | productivity | Yes | builtin | Edit PDF text via nano-pdf CLI | nano-pdf | Low | OPTIONAL |
| notion | productivity | Yes | builtin | Notion API + ntn CLI | Notion token | Low | OPTIONAL |
| ocr-and-documents | productivity | Yes | builtin | OCR from PDFs/scans (pymupdf) | pymupdf | Low | KEEP-USEFUL |
| powerpoint | productivity | Yes | builtin | Create/read/edit .pptx decks | python-pptx | Low | KEEP-USEFUL |
| teams-meeting-pipeline | productivity | Yes | builtin | Teams meeting summary pipeline | Teams API | Medium | DISABLE-UNUSED |
| arxiv | research | Yes | builtin | Search arXiv papers by keyword | arxiv API | Low | KEEP-USEFUL |
| blogwatcher | research | Yes | builtin | Monitor blogs and RSS/Atom feeds | blogwatcher | Low | KEEP-USEFUL |
| llm-wiki | research | Yes | builtin | Karpathy's LLM Wiki (interlinked) | None | Low | KEEP-USEFUL |
| polymarket | research | Yes | builtin | Query Polymarket prediction markets | Polymarket API | Low | OPTIONAL |
| research-paper-writing | research | Yes | builtin | Write ML papers (NeurIPS/ICML) | None | Low | OPTIONAL |
| openhue | smart-home | Yes | builtin | Control Philips Hue lights | Hue hub + key | Low | DISABLE-UNUSED |
| xurl | social-media | Yes | builtin | X/Twitter via xurl CLI | X API key | Medium (social posting) | OPTIONAL |
| hermes-agent-skill-authoring | software-development | Yes | builtin | Author in-repo SKILL.md | None | Low | KEEP-CORE |
| node-inspect-debugger | software-development | Yes | builtin | Debug Node.js via --inspect | Node.js | Low | KEEP-USEFUL |
| plan | software-development | Yes | builtin | Plan mode: write actionable markdown plan | None | Low | KEEP-CORE |
| python-debugpy | software-development | Yes | builtin | Debug Python via pdb/debugpy | debugpy | Low | KEEP-USEFUL |
| requesting-code-review | software-development | Yes | builtin | Pre-commit security scan/quality gates | gh CLI | Low | KEEP-CORE |
| simplify-code | software-development | Yes | builtin | 3-agent parallel code cleanup | None | Low | KEEP-USEFUL |
| spike | software-development | Yes | builtin | Throwaway experiments before committing | None | Low | KEEP-CORE |
| systematic-debugging | software-development | Yes | builtin | 4-phase root cause debugging | None | Low | KEEP-CORE |
| test-driven-development | software-development | Yes | builtin | TDD: RED-GREEN-REFACTOR enforcement | None | Low | KEEP-CORE |
| yuanbao | yuanbao | Yes | builtin | Yuanbao Chinese platform groups/queries | Yuanbao app | Low | DISABLE-UNUSED |

---

## Optional Skills (sampled by category)

| Skill | Category | Origin | Description | Risk | Recommendation |
|---|---|---|---|---|---|
| antigravity-cli | optional/autonomous | official | Antigravity CLI agy: plugins, sandbox | Medium | REVIEW-MANUAL |
| blackbox | optional/autonomous | community | Delegate to Blackbox AI CLI | Medium (external AI) | OPTIONAL |
| grok | optional/autonomous | official | Delegate to xAI Grok Build CLI | Low | INSTALL-CANDIDATE |
| honcho | optional/autonomous | official | Honcho cross-session memory | Low | INSTALL-CANDIDATE |
| openhands | optional/autonomous | official | Delegate to OpenHands LiteLLM | Low | INSTALL-CANDIDATE |
| evm | optional/blockchain | community | Read-only EVM client | Medium (keys) | DISABLE-RISKY |
| hyperliquid | optional/blockchain | community | Hyperliquid market data | Medium | DISABLE-RISKY |
| solana | optional/blockchain | community | Solana blockchain data queries | Medium | DISABLE-RISKY |
| docker-management | optional/devops | official | Docker containers/images/compose | Low | INSTALL-CANDIDATE |
| watchers | optional/devops | official | Poll RSS, JSON APIs, GitHub watchers | Low | INSTALL-CANDIDATE |
| fastmcp | optional/mcp | official | Build/deploy MCP servers with FastMCP | Low | INSTALL-CANDIDATE |
| mcporter | optional/mcp | official | Configure/call MCP servers via CLI | Low | INSTALL-CANDIDATE |
| duckduckgo-search | optional/research | official | Free DuckDuckGo web search, no key | Low | INSTALL-CANDIDATE |
| searxng-search | optional/research | official | Meta-search via SearXNG, no key | Low | INSTALL-CANDIDATE |
| scrapling | optional/research | official | Web scraping + stealth browser | Medium | INSTALL-CANDIDATE |
| osint-investigation | optional/research | official | Public-records OSINT (SEC, EDGAR) | Low | INSTALL-CANDIDATE |
| domain-intel | optional/research | official | Passive domain recon (stdlib only) | Low | INSTALL-CANDIDATE |
| code-wiki | optional/software-dev | official | Wiki + Mermaid diagrams for codebase | Low | INSTALL-CANDIDATE |
| subagent-driven-development | optional/software-dev | official | Execute plans via delegate_task subagents | Low | INSTALL-CANDIDATE |
| rest-graphql-debug | optional/software-dev | official | Debug REST/GraphQL APIs | Low | INSTALL-CANDIDATE |
| 1password | optional/security | official | 1Password CLI op | Low (read-only) | KEEP-USEFUL |
| godmode | optional/security | community | Jailbreak LLMs | HIGH | DISABLE-RISKY |
| web-pentest | optional/security | community | Web penetration testing | HIGH | DISABLE-RISKY |
| oss-forensics | optional/security | community | Empty/stub SKILL.md | Unknown | BROKEN |
| sherlock | optional/security | official | OSINT username search | Low | OPTIONAL |
| finance/excel-author | optional/finance | official | Build Excel models headless | Low | OPTIONAL |
| finance/stocks | optional/finance | official | Stock quotes via Yahoo Finance | Low | OPTIONAL |
| finance/dcf-model | optional/finance | official | DCF valuation models | Low | OPTIONAL |
| meme-generation | optional/creative | official | Generate meme images with Pillow | Low | OPTIONAL |
| concept-diagrams | optional/creative | official | Educational SVG diagrams | Low | KEEP-USEFUL |
| creative-ideation | optional/creative | official | Ideas via named creative methods | Low | OPTIONAL |
| kanban-video-orchestrator | optional/creative | official | Multi-agent video production pipeline | Low | OPTIONAL |
| blender-mcp | optional/creative | official | Control Blender via socket/MCP | Medium (local Blender) | OPTIONAL |
| bioinformatics | optional/research | official | Gateway to 400+ bioinformatics skills | Low | OPTIONAL |
| openclaw-migration | optional/migration | official | Migrate OpenClaw to Hermes | Low | REVIEW-MANUAL |
| gaming/minecraft-modpack-server | optional/gaming | community | Host modded Minecraft servers | Medium | DISABLE-UNUSED |
| gaming/pokemon-player | optional/gaming | community | Play Pokemon via headless emulator | Medium | DISABLE-UNUSED |
| health/fitness-nutrition | optional/health | community | Fitness/nutrition tracking (stub) | Unknown | BROKEN |
| health/neuroskill-bci | optional/health | community | BCI (stub) | Unknown | BROKEN |
| payments/stripe-link-cli | optional/payments | official | Agent payments via Stripe Link | High (financial) | REVIEW-MANUAL |
| payments/stripe-projects | optional/payments | official | Provision SaaS services + Stripe | High (financial) | REVIEW-MANUAL |
| payments/mpp-agent | optional/payments | official | HTTP 402 via Machine Payments Protocol | High (financial) | REVIEW-MANUAL |
| communication/one-three-one-rule | optional/communication | official | 1-3-1 rule structured communication | Low | OPTIONAL |
| inference-sh-cli | optional/devops | official | 150+ AI apps via inference.sh | Low | OPTIONAL |
| here-now | optional/productivity | official | Publish static sites + agent handoff | Low | OPTIONAL |

---

## Summary Counts

| Classification | Count (core) | Count (optional) |
|---|---|---|
| KEEP-CORE | 17 | 0 |
| KEEP-USEFUL | 23 | 3 |
| DISABLE-UNUSED | 7 | 4 |
| DISABLE-RISKY | 1 (macos-computer-use) | 5 |
| OPTIONAL | 19 | 25 |
| REVIEW-MANUAL | 0 | 5 |
| INSTALL-CANDIDATE | 0 | 11 |
| BROKEN | 0 | 3 |
| DUPLICATE | 0 | 0 |
