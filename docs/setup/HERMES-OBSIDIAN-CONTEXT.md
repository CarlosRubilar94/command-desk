# Hermes Obsidian Context Bridge

> File: `agent/obsidian_context.py`
> Status: **READY** (read-only, no credentials required)

---

## What it does

`ObsidianContextBridge` extracts **operational context only** from an Obsidian
vault so Hermes can ground orchestration decisions in documented project state.

**It is strictly read-only:**
- Never writes to the vault
- Never copies sensitive note content into Hermes memory or logs
- Extracts: folder structure, note titles, YAML front-matter **keys** (never values), short summaries (≤3 sanitized lines)
- Actively strips lines matching common credential patterns (`api_key`, `sk-`, `cursor_`, `password`, etc.)

## Configuration

```bash
# Set vault path (defaults to ~/Documents/Obsidian or OBSIDIAN_VAULT_PATH)
export OBSIDIAN_VAULT_PATH="G:/Meu Drive/03-Documentacao/Obsidian-DevSSD"
```

Or pass `vault_path` directly:

```python
from agent.obsidian_context import ObsidianContextBridge

bridge = ObsidianContextBridge(
    vault_path="G:/Meu Drive/03-Documentacao/Obsidian-DevSSD",
    operational_paths=(
        "00-AI/START-HERE.md",
        "00-AI/working-context.md",
        "09-Missoes/Missoes OpenClaw.md",
    ),
)
ctx = bridge.load()
print(ctx.summary_text)   # inject into Hermes system prompt
```

## Relationship to control-center collector

`control-center/lib/collectors/obsidian.js` is the richer JS pipeline
collector.  `agent/obsidian_context.py` is the Hermes-side read path —
it reads the vault directly via Python stdlib with no Node dependency.
The two are complementary, not duplicates.

## Security

| Concern | Mitigation |
|---|---|
| Secret content in notes | Lines matching credential patterns → stripped from summary |
| YAML values | Only keys extracted; values never read into output |
| Vault writes | No write operations anywhere in the module |
| Large vaults | Max 200 notes per folder; folder walk is bounded by OS glob |

## Tests

```bash
uv run pytest tests/test_obsidian_context.py -v
# 19 passed
```
