# Command Desk Gateway — DevSSD

O **gateway** expõe a API de mensagens/agente em loopback (`:8642`) e integra plataformas (Telegram, Discord, etc.).

## Status rápido

| Check | Comando / URL |
| --- | --- |
| Dashboard | http://127.0.0.1:9119 — `gateway_running` no `/api/status` |
| API health | http://127.0.0.1:8642/health |
| CLI | `command-desk gateway status` |
| Doctor | `integrations\command-deck\scripts\command-desk-doctor.ps1` |

## Estados comuns

| Estado | Dashboard | API :8642 | Ação |
| --- | --- | --- | --- |
| Dashboard only | `gateway_running: false` | offline | Normal após start; agente one-shot (`-z`) e doctor funcionam sem gateway |
| Gateway up | `gateway_running: true` | `{"status":"ok"}` | Pronto para messaging / API server |
| Installed task | `gateway_state: installed` | pode variar | Scheduled Task criada; reinício automático no boot |

## Iniciar (manual)

```powershell
# Via Command Deck (UI ou API task) — control-center sibling
..\control-center\scripts\command-desk-gateway-start.ps1

# Ou deste repo
.\integrations\command-deck\scripts\command-desk-gateway-start.ps1

# Ou direto
command-desk gateway start
```

## Instalar auto-start (interativo)

```powershell
command-desk gateway install   # cria Scheduled Task Windows
```

## Command Deck

- Card **Command Desk** mostra `available: true` quando dashboard :9119 responde (não exige gateway).
- Task `command-desk-gateway-start` no Deck — confirmação recomendada (expõe API local).

## Troubleshooting

1. **Doctor OK, gateway offline** — esperado; use `gateway start` ou task do Deck.
2. **API 8642 não responde após start** — aguarde ~5s; verifique `gateway status`.
3. **One-shot `-z` falha 429** — rate limit OpenRouter; troque modelo free.
4. **Secrets** — `bitwarden-env-sync.ps1` (control-center) antes de CLI; nunca commitar `.env`.
