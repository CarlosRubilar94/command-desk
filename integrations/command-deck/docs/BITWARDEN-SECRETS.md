# Bitwarden Secrets Manager — DevSSD

Fonte de verdade para API keys do DevSSD: [Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/) via `command-desk` + `bws`.

**Bootstrap local:** apenas `BWS_ACCESS_TOKEN` em `%USERPROFILE%\.command-desk\.env`.  
**Nunca** commitar secrets; logs usam `****last4`.

## Passo manual (uma vez) — access token

1. [Secrets Manager](https://vault.bitwarden.com/#/sm/)
2. Projeto **`DevSSD-keys`** (criar se não existe)
3. Machine account **`command-desk-dev`** → Projects → **Read** em `DevSSD-keys`
4. Access tokens → Create → copiar token `0.…` (só aparece uma vez)

Conta EU? `--server-url https://vault.bitwarden.eu`

## Bootstrap automático (após token)

Scripts completos ficam no repositório **control-center** (Command Deck):

```powershell
cd <control-center>
.\scripts\bitwarden-sm-bootstrap.ps1 -AccessToken '0.SEU_TOKEN' -ProjectId 'UUID-DO-PROJETO'
```

Ou interativo (token não aparece no histórico):

```powershell
.\scripts\bitwarden-sm-bootstrap.ps1
```

## Uso diário

### Sincronizar env para Cursor / MCPs

```powershell
. <control-center>\scripts\bitwarden-env-sync.ps1
```

### command-desk nativo

Com `enabled: true`, cada `command-desk` / `hermes` puxa secrets no startup.

```powershell
command-desk secrets bitwarden status
command-desk secrets bitwarden sync          # dry-run
command-desk secrets bitwarden sync --apply
```

## Config (`~/.command-desk/config.yaml`)

```yaml
secrets:
  bitwarden:
    enabled: true
    access_token_env: BWS_ACCESS_TOKEN
    project_id: "<uuid>"
    server_url: ""
    override_existing: true
    auto_install: true
```

## Validação

```powershell
command-desk secrets bitwarden status
command-desk doctor
bws secret list <project-id>   # com BWS_ACCESS_TOKEN no env
```

## Segurança

- Revogar token comprometido: SM web → machine account → access tokens → revoke → novo token.
- Nunca commitar `.env`, tokens BWS, ou chaves API em texto claro.

## Referências

- Upstream: `website/docs/user-guide/secrets/bitwarden.md`
- Command Deck scripts: `control-center/scripts/bitwarden-*.ps1`
