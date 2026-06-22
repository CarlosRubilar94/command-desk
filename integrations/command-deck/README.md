# Command Deck integration (DevSSD)

**Command Desk** (this repo) is the persistent AI agent — skills, memory, gateway, cron, web dashboard (`:9119`).

**Command Deck** is the operational dashboard (sibling repo `control-center`, port `:8765`) that monitors DevSSD services including Command Desk.

## Layout

| Path | Purpose |
| --- | --- |
| `collector-contract/command-desk.js` | Collector contract for Command Deck aggregator |
| `docs/` | Bitwarden + gateway runbooks (no secrets) |
| `scripts/` | PowerShell helpers (start, doctor, smoke, gateway) |

## Command Deck repo (sibling)

The full Command Deck app lives separately:

```
../control-center/          # or clone your own control-center repo
  lib/collectors/command-desk.js   # copy from collector-contract/ when updating
  server.js                        # dashboard API :8765
  scripts/command-desk-*.ps1       # may mirror integrations/command-deck/scripts/
```

To wire the collector in Command Deck, copy or symlink:

```powershell
Copy-Item integrations\command-deck\collector-contract\command-desk.js `
  ..\control-center\lib\collectors\command-desk.js
```

## Ports

| Service | URL |
| --- | --- |
| Command Desk dashboard | http://127.0.0.1:9119 |
| Command Desk gateway API | http://127.0.0.1:8642 |
| Command Deck dashboard | http://127.0.0.1:8765 |

## Quick ops (from this repo)

```powershell
.\integrations\command-deck\scripts\command-desk-start.ps1
.\integrations\command-deck\scripts\command-desk-doctor.ps1
.\integrations\command-deck\scripts\command-desk-smoke.ps1
```

Set `$env:COMMAND_DESK_REPO` if the checkout is not the default sibling path.
