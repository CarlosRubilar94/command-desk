# Maestro — Orquestração Email → WhatsApp (DOC DE ARQUITETURA)

> **Status:** proposta de arquitetura / pesquisa (NÃO implementado).
> **Escopo:** assistente conversacional ("Maestro") que lê múltiplas caixas de e-mail
> (Gmail pessoal + empresa, Hostinger pessoal + empresa), entrega um **resumo + ideias
> acionáveis** no WhatsApp pessoal, e permite **analisar/ajustar/apagar e-mails e marcar
> eventos de agenda** por conversa no WhatsApp — com **economia de token** e usando os
> planos pagos já existentes.
> **Repo:** fork `command-desk` (Hermes Agent) — `CarlosRubilar94/command-desk`, base `devssd/command-desk`.

---

## TL;DR — Recomendação

1. **Não construir do zero.** O Command-Desk/Hermes **já** traz, nativamente, quase toda a
   infraestrutura: adapter **WhatsApp (bridge Baileys)** e **WhatsApp Cloud API (oficial)**,
   **adapter de e-mail IMAP/SMTP**, **skill Himalaya** (IMAP/SMTP multi-conta via CLI),
   **cron/automações** (ticker 60s + Chronos scale-to-zero), **MCP com OAuth**
   (`user-google-tools` = Gmail/Calendar completos), **aprovação de ações perigosas**
   (`/approve` `/deny`), mitigação de **prompt-injection** em cron e camada de segurança
   (`tirith_security`, allowlists, DM pairing). O "Maestro" é **uma fina camada de
   orquestração** (1–3 cron jobs + 1 skill/prompt), não um serviço novo.
2. **Canal WhatsApp recomendado:** **bridge Baileys nativo do Hermes** em **modo
   `self-chat`** no número pessoal para o MVP (zero custo, conversa de mão dupla, mantém o
   app normal funcionando). Caminho de evolução para **WhatsApp Cloud API oficial** num
   **número dedicado** quando quiser estabilidade/zero-risco-de-ban. Detalhes e ressalvas na §3.
3. **Onde roda:** **opção (a) — automação/cron dentro do Hermes**, com o `gateway` rodando
   como serviço no **servidor Hetzner** (Linux). É a de menor esforço e reaproveita
   sessão, MCP, aprovação e segurança. n8n e "serviço dedicado" ficam como complementos
   opcionais, não como base (§4).
4. **Economia de token:** pipeline de **dois níveis** — triagem/classificação/resumo em
   **modelo barato** (Gemini Flash via key já no `.env`, ou modelo barato no OpenRouter);
   **raciocínio/decisão** só quando necessário em **Claude** (via OpenRouter ou Anthropic
   key). Processar só **não-lidos / últimas N horas**, **metadata antes de corpo**,
   **batch**, **dedupe por thread**, **truncagem**, **cache de IDs processados** (§4).

> ⚠️ **Ressalva de credencial de IA:** o **Claude Pro (OAuth)** e o **Codex (OAuth)** estão
> atrelados aos respectivos **CLIs** e **não** plugam diretamente como *provider HTTP* do
> Hermes. Para "Claude" no pipeline, usar **OpenRouter** (créditos) ou **Anthropic API key**.
> O caminho barato se apoia nas keys **GEMINI/GOOGLE** e **OPENROUTER** já presentes no `.env` do Hermes.

---
## 0. Descobertas-chave (confirmadas lendo o ambiente)

| Capacidade | Situação no ambiente | Fonte |
|---|---|---|
| Gmail (ler/listar/rotular/arquivar/lixeira/apagar/enviar/draft) | **Completo** via MCP `user-google-tools` | descritores `tools/*.json` |
| Calendar (criar/editar/mover/listar/excluir evento) | **Completo** via mesmo MCP | `manage_event`, `move_event`, `get_events`, `list_calendars` |
| Multi-conta Google (pessoal + empresa) no MCP | **NÃO suportado** (sessão OAuth única; há `logout`, sem parâmetro `account` em nenhum tool) | ver §1 |
| E-mail IMAP/SMTP genérico (Hostinger) | **Suportado** via skill **Himalaya** (multi-conta) e/ou adapter de e-mail do gateway | `skills/email/himalaya`, `messaging/email.md` |
| WhatsApp 2-vias (receber+enviar) | **Nativo** — bridge Baileys (`hermes whatsapp`) e Cloud API (`hermes whatsapp-cloud`) | `messaging/whatsapp.md`, `whatsapp-cloud.md` |
| Agendamento (cron) que dispara um turno de agente | **Nativo** (ticker 60s + Chronos one-shot/scale-to-zero) | `cron/scheduler.py`, `docs/chronos-managed-cron-contract.md` |
| Confirmação de ação perigosa | **Nativo** (`/approve` `/deny`, `write_approval`, `slash_confirm`) | `messaging/index.md`, `tools/` |
| Defesa prompt-injection / segurança | **Presente** (`tirith_security`, `threat_patterns`, testes de cron prompt-injection) | `tools/`, `tests/cron/` |
| Economia de token embutida | **Sim** (debounce/batch de mensagens WhatsApp, `/compress`, reset de sessão, silence tokens, `maxBodyChars`) | `messaging/whatsapp.md`, `index.md` |

**Conclusão:** o trabalho é majoritariamente **configuração + orquestração + prompt design**,
não engenharia de plataforma.

---

## 1. Inventário Gmail / Calendar via MCP `user-google-tools`

O MCP expõe a superfície **Gmail + Calendar (+ Tasks, Drive, Docs, Sheets, Slides, Forms)**.
Para o Maestro, os relevantes:

### 1.1 Gmail — operações disponíveis (nomes reais dos tools)

| Categoria | Tools | Observações p/ economia/segurança |
|---|---|---|
| Listar | `list_messages`, `list_threads`, `batch_get_threads`, `batch_get_messages` | `q` aceita query Gmail (`is:unread`, `newer_than:1d`); `format` = `metadata`/`clean`/`full`; `maxBodyChars` (default **3000**, `0`=ilimitado) → **triagem barata só com metadata** |
| Ler | `get_message`, `get_thread`, `get_attachment` | `format=clean` devolve from/to/subject/date/body achatado; `bodyTruncated:true` quando cortado |
| Rotular / arquivar / marcar lido | `modify_message`, `modify_thread` (`addLabelIds`/`removeLabelIds`) | arquivar = remover label `INBOX`; marcar lido = remover `UNREAD` — **reversível** |
| Lixeira (reversível) | `trash_message`, `trash_thread` (`action: trash` / `untrash`) | **caminho padrão para "apagar"** — recuperável |
| Apagar (permanente) | `delete_message`, `delete_thread` | **destrutivo irreversível** — usar só com dupla confirmação explícita |
| Enviar / responder | `send_message`, `reply_message`, `forward_message` | |
| Rascunhos | `create_draft`, `update_draft`, `get_draft`, `list_drafts`, `delete_draft`, `send_draft` | útil para "preparar resposta p/ revisão" |
| Labels | `create_label`, `get_label`, `list_labels`, `patch_label`, `delete_label` | criar label `Maestro/Processado`, `Maestro/Ação` |
| Identidades de envio | `*_send_as` (create/get/list/patch/update/verify/delete) | |
| Push/watch | `watch_mailbox`, `stop_mail_watch` | alternativa a polling (requer Pub/Sub) — opcional, fase avançada |

### 1.2 Calendar — operações

| Tool | Função |
|---|---|
| `manage_event` (`action: create/update/delete`) | **criar/editar/excluir** evento; suporta `summary`, `start_time`/`end_time` (RFC3339), `timezone`, `attendees`, `add_google_meet`, `reminders`, `recurrence` (RRULE), `visibility`, `send_updates` |
| `move_event` | mover evento entre calendários |
| `get_events` | listar eventos (leitura de agenda) |
| `list_calendars` | listar calendários (default `primary`) |
| `manage_calendar` | criar/gerir calendários |
| `list_recurring_event_instances` | instâncias de evento recorrente |

> Para "marcar evento" basta `manage_event action=create` com `timezone: America/Sao_Paulo`.
> **Sempre `update`** para alterar (preserva ID/RSVP), nunca delete+recreate.

### 1.3 Limitação crítica: **conta única**

O `user-google-tools` opera sobre **uma** identidade Google (OAuth única; existe `logout`,
e **nenhum** tool aceita seletor de conta). Logo, **Gmail pessoal e Gmail da empresa não
coexistem** no mesmo MCP simultaneamente.

**Alternativas para multi-conta Google:**
- **(A) recomendada p/ leitura/triagem:** tratar a 2ª conta Google via **IMAP** (app
  password do Google) na **skill Himalaya** — unifica com as caixas Hostinger (§2). Cobre
  listar/ler/rotular/mover/**apagar**.
- **(B)** segunda **instância do MCP** autenticada na 2ª conta (se o runtime permitir 2
  servidores google-tools com `serverIdentifier` distinto). Mantém ações ricas de Calendar
  na conta empresa, ao custo de 2 OAuth.
- **(C)** chamar a **Gmail/Calendar API diretamente** com 2 tokens OAuth numa automação
  custom (mais trabalho; só se precisar de Calendar avançado nas 2 contas).

> **Decisão pendente do usuário:** a conta "empresa" é Gmail/Workspace? Quer ações de
> **Calendar** nela (então B/C) ou só **e-mail** (então A via IMAP)?

---
## 2. Hostinger e-mail (pessoal + empresa) para automação

### 2.1 Servidores IMAP/SMTP

| Provedor da caixa | IMAP | SMTP | Encriptação |
|---|---|---|---|
| **Hostinger Email** (padrão atual) | `imap.hostinger.com` : **993** | `smtp.hostinger.com` : **465** | **SSL/TLS** |
| **Titan** (algumas contas Hostinger antigas/migradas) | `imap.titan.email` : **993** | `smtp.titan.email` : **465** | **SSL/TLS** |

> **Decisão pendente:** confirmar, por conta, se é **Hostinger Email** ou **Titan**
> (define o host). POP existe (`pop.hostinger`/`pop.titan` : 995) mas **IMAP é o correto**
> (não baixa/remove do servidor).

### 2.2 App password (obrigatório/recomendado)

- Criar **app password por mailbox** no **hPanel** → *Emails* → domínio → *Mailboxes* →
  menu ⋮ → **App passwords** → *Generate* (nomear ex. `maestro`). Revogável a qualquer
  momento sem afetar a senha principal.
- Se **2FA** estiver ligado, o app password é **obrigatório** (Titan bloqueia 3rd-party com
  2FA até habilitar "Titan on other apps").
- **Uma app password para a conta pessoal e outra para a conta empresa** (são caixas
  separadas).

### 2.3 Integração (libs / mecanismo)

- **Recomendado:** **skill Himalaya** (bundled no Hermes, MIT, multi-conta via
  `~/.config/himalaya/config.toml` com `[accounts.pessoal]`, `[accounts.empresa]`, …). Dá
  ao agente list/read/move/**delete**/send por conta, via terminal tools — cobre Hostinger
  pessoal+empresa **e** a 2ª conta Google por IMAP, num só lugar.
- **Alternativa programática:** Python `imaplib`/`email` (stdlib) ou **`IMAPClient`** (API
  mais limpa) + `smtplib`/`aiosmtplib` numa automação custom — útil se quiser
  ingestão/triagem 100% em código sem passar pelo LLM.
- **Adapter de e-mail do gateway** (`messaging/email.md`, usa `imaplib`/`smtplib`): serve
  para "alguém manda e-mail pro agente e ele responde" — é **single-account** e marca tudo
  como lido no boot; **não** é o caminho para *triagem de inbox multi-conta*. Citado para
  evitar confusão.

> Faltando capacidade no MCP Google (multi-conta) → **IMAP/Himalaya é a alternativa** que
> também resolve apagar/arquivar nas contas não-Google.

---

## 3. WhatsApp 2 vias para o número PESSOAL

### 3.1 Comparativo

| Opção | Recebe+Envia | Nº pessoal? | Risco/ToS | Custo | Setup | Brasil |
|---|---|---|---|---|---|---|
| **Bridge Baileys (nativo Hermes)** | ✅ (streaming, voz, batch) | ✅ via **Linked Device** (self-chat) — app normal continua | ⚠️ **não-oficial, risco de ban** (baixo em uso pessoal/baixo volume) | **grátis** | **baixíssimo** (`hermes whatsapp`, QR) | ✅ comunidade enorme |
| **Evolution API** (Baileys, self-host Hetzner) | ✅ (webhooks) | ✅ Linked Device | ⚠️ mesmo risco; REST + multi-instância | grátis (self-host) | médio (Docker no Hetzner) | ✅ origem/uso BR forte |
| **WAHA** (Baileys/whatsmeow, Docker) | ✅ | ✅ Linked Device | ⚠️ mesmo risco | grátis/own | médio | ok |
| **Meta WhatsApp Cloud API (oficial)** | ✅ (webhook HTTPS) | ❌ **não no nº pessoal** — migração **só-ida**, perde o app de consumidor; exige **nº dedicado** | ✅ **zero ban**; verificação de negócio | **grátis dentro da janela 24h**; fora dela só **template** (utility BR ≈ **US$0,008**/msg; service grátis) | alto (Meta Business + URL pública + template) | ✅ preços em BRL (migração até 2027) |
| **Twilio WhatsApp** (BSP do oficial) | ✅ | ❌ nº dedicado/WABA | ✅ baixo (oficial) | pago por msg + markup BSP | médio (sandbox p/ teste) | ✅ |

### 3.2 Recomendação

**MVP → Bridge Baileys nativo do Hermes, modo `self-chat`, no número pessoal.**
Justificativa:
- **Mão dupla real** (recebe e envia), **streaming**, **transcrição de voz**, **debounce/
  batch** (economia de token) — tudo pronto, `hermes whatsapp` + QR em *Linked Devices*.
- **Mantém o WhatsApp normal funcionando** no mesmo número (é um dispositivo vinculado),
  ao contrário da Cloud API (que exige migrar o número e perder o app).
- **Custo zero** e self-host no Hetzner (a sessão fica em `~/.hermes/platforms/whatsapp/session`).
- O risco de ban do Baileys é **real porém baixo** neste perfil: **destinatário único = você
  mesmo**, **sem bulk/marketing**, **sem outbound não solicitado**, volume baixo — exatamente
  as mitigações que a doc do Hermes e as fontes recomendam.

**Mitigações de ban:** número aquecido; só conversa (nada de disparo em massa); allowlist
`WHATSAPP_ALLOWED_USERS` = só seu número; `whatsapp.unauthorized_dm_behavior: ignore`;
monitorar logs/`bridge.log` e re-parear se cair.

**Evolução (quando quiser robustez/zero-risco):** migrar para **WhatsApp Cloud API** num
**número dedicado** (chip pré-pago/eSIM/Google Voice). O resumo diário proativo passa a usar
um **template "utility"** (barato/►grátis se dentro de janela de 24h aberta por uma sua msg).
Hermes já tem o adapter `hermes whatsapp-cloud`. **Evolution API** só se você precisar de
REST/multi-instância fora do Hermes — caso contrário o bridge nativo já entrega.

> **Decisão pendente:** (a) começar no **número pessoal (self-chat, risco baixo)** ✅ recomendado,
> ou (b) já dedicar um **segundo número** (mais setup, zero risco no futuro com Cloud API)?

---
## 4. Arquitetura Maestro + economia de token

### 4.1 Pipeline (ingestão → triagem barata → resumo → sugestões → ações)

```
[cron Hermes ~07:30 BRT]
   │
   ├─(1) INGESTÃO (só não-lidos / últimas N horas, por conta)
   │     • Gmail pessoal  → MCP user-google-tools: list_threads q="is:unread newer_than:16h" format=metadata
   │     • Gmail empresa   → Himalaya (IMAP app password)  [ou 2º MCP]
   │     • Hostinger pess. → Himalaya conta "pessoal"
   │     • Hostinger emp.  → Himalaya conta "empresa"
   │
   ├─(2) NORMALIZAÇÃO → registros compactos {conta, de, assunto, snippet, data, threadId, msgId, labels}
   │     • dedupe por thread; corta assinatura/quoted/HTML; cap N e-mails/execução
   │
   ├─(3) TRIAGEM BARATA  [MODELO BARATO: Gemini Flash / OpenRouter barato]
   │     • classifica cada item: {prioridade, categoria, precisa_ação?, ação_sugerida}
   │     • entrada = SÓ metadata+snippet (sem corpo) → barato
   │
   ├─(4) RESUMO + IDEIAS  [MODELO BARATO/MÉDIO]
   │     • busca corpo (format=clean, maxBodyChars) APENAS dos itens que passaram na triagem
   │     • gera digest agrupado por conta/prioridade + ideias acionáveis
   │       ex.: "📅 marcar agenda: reunião com Fulano ter 10h", "🗑️ 4 newsletters p/ lixeira"
   │
   ├─(5) ENTREGA no WhatsApp pessoal (bridge Baileys) — texto WhatsApp-markdown, chunked
   │
   └─(6) AÇÕES CONVERSACIONAIS (sob demanda, ao você responder)
         • seu texto → AIAgent [Claude p/ raciocínio] com tools MCP/Himalaya/Calendar
         • toda ação destrutiva passa por dry-run + /approve (§5)
```

### 4.2 Modelo por etapa (custo vs. capacidade)

| Etapa | Modelo | Por quê |
|---|---|---|
| Triagem / classificação | **Gemini Flash** (key `GEMINI/GOOGLE` no `.env`) **ou** modelo barato OpenRouter | volume alto, tarefa simples, entrada curta |
| Sumarização / agrupamento | **barato→médio** (Flash / `gpt-mini`-class via OpenRouter) | texto maior, ainda barato |
| Raciocínio / decisão / ações ambíguas | **Claude** (OpenRouter créditos **ou** Anthropic key) | qualidade em decisão/escrita; só nos itens que exigem |
| Conversa no WhatsApp (default) | médio; `/model` troca on-the-fly | equilíbrio custo/latência |

> Trocar modelo por sessão com `/model provider:model` (nativo). O **Claude Pro/Codex OAuth
> não é provider HTTP** do Hermes (vide ressalva do TL;DR).

### 4.3 Estratégias de redução de token

- **Só não-lidos / janela curta:** Gmail `q="is:unread newer_than:16h"`; IMAP `UNSEEN SINCE`.
- **Metadata antes de corpo:** `format=metadata` na triagem; corpo (`format=clean`,
  `maxBodyChars` ~800–1500) só nos aprovados.
- **Batch:** `batch_get_messages`/`batch_get_threads` (menos round-trips).
- **Dedupe por thread:** resumir a thread uma vez, não msg a msg.
- **Limpeza:** remover assinaturas, quoted replies e HTML antes do LLM.
- **Cap rígido:** N máx de e-mails/execução; truncar corpos longos.
- **Cache de processados:** persistir `msgId → classificação/resumo` (store de jobs/SQLite
  ou label `Maestro/Processado`) p/ **não reprocessar**; o follow-up conversacional lê o
  cache em vez de re-buscar tudo.
- **Built-ins do Hermes:** debounce/batch de WhatsApp, `/compress`, reset de sessão, silence
  tokens (turnos sem entrega).

### 4.4 Onde roda — (a) Hermes vs (b) serviço Hetzner vs (c) n8n

| Opção | Prós | Contras | Veredito |
|---|---|---|---|
| **(a) Automação/cron no Hermes** (gateway como serviço no Hetzner) | reaproveita WhatsApp, e-mail, MCP, cron, **aprovação**, segurança, sessão; **mínimo código novo**; estado de conversa nativo | acoplado ao Hermes | ✅ **RECOMENDADO (base)** |
| **(b) Serviço dedicado no Hetzner** | controle total | **reinventa** messaging/sessão/cron/approval; mais segredos; mais manutenção | só se "sair" do Hermes |
| **(c) n8n** | low-code, nodes prontos (Gmail/IMAP/Evolution/Cloud API), ótimo p/ *plumbing* não-IA | agente conversacional + tool-use + aprovação ficam toscos; ainda precisa de LLM atrás | complemento opcional (ex.: trigger IMAP), não a base |

**Recomendação:** **(a)**. O `gateway` roda como **systemd service** no Hetzner
(`hermes gateway install --system` / user-service + linger). n8n entra **depois**, só se você
quiser orquestrar plumbing visual; a **decisão/raciocínio fica no Hermes**.

---
## 5. Fluxo conversacional + segurança

### 5.1 Como você interage (linguagem natural + atalhos)

- **Linguagem natural:** "resume de novo só os do trabalho", "arquiva as newsletters",
  "joga fora os 3 de promoção", "marca reunião com a Ana quinta 15h", "responde o cliente
  dizendo que envio amanhã".
- **Atalhos/slash (nativos):** `/approve` `/deny` (confirmar/negar ação), `/undo`
  (remove último turno), `/stop`, `/model`, `/status`, `/usage` (ver gasto de token).
- O digest pode trazer **itens numerados** → "apaga 2 e 5", "agenda o 3".

### 5.2 Tratamento SEGURO de ações destrutivas (apagar/arquivar)

Princípios (defaults conservadores):

1. **Confirmação obrigatória por padrão.** Toda ação que muda estado (apagar, arquivar,
   marcar lido em massa, criar evento, enviar e-mail) **só executa após `/approve`**.
   Hermes já tem o gate `/approve` `/deny` + `write_approval`/`slash_confirm`.
2. **Dry-run primeiro.** O agente **lista o que VAI fazer** ("vou mover p/ lixeira estes 4:
   …") e aguarda confirmação. Nada de ação silenciosa.
3. **"Apagar" = lixeira, não delete permanente.** Mapear pedido de apagar para
   **`trash_message`/`trash_thread`** (reversível). **`delete_message`/`delete_thread`
   (permanente) só com dupla confirmação explícita** ("apagar PERMANENTEMENTE? confirme").
4. **Undo quando possível.** Lixeira → `trash action=untrash`; arquivar/marcar lido →
   re-`modify` labels; manter **registro da última ação** (msgIds + operação) p/ "desfaz".
5. **Log de auditoria.** Cada ação → linha em `~/.hermes/logs/maestro-audit.jsonl`
   (timestamp, conta, operação, ids, origem=quem pediu). Some-se aos logs/transcript nativos.
6. **Allowlist + privacidade.** `WHATSAPP_ALLOWED_USERS` = só seu número;
   `unauthorized_dm_behavior: ignore`; proteger a pasta de sessão (`chmod 700`).
7. **Prompt-injection (e-mail é dado, não comando).** O corpo do e-mail é **conteúdo não
   confiável**: delimitar claramente no prompt, instruir o modelo a **nunca** executar
   instruções contidas em e-mails, e **só** agir a partir do **seu** comando no WhatsApp.
   Hermes já tem mitigações de prompt-injection em cron + `tirith_security`/`threat_patterns`.

### 5.3 Fluxo de criar evento de agenda

```
Você: "marca reunião com a Ana quinta 15h, 1h, no Meet"
Maestro (dry-run): "📅 Criar em 'primary':
   Título: Reunião com Ana | 2026-06-25 15:00–16:00 (America/Sao_Paulo)
   Google Meet: sim | Convidados: ana@... | Lembrete: 10min
   Confirmar? /approve"
Você: /approve
Maestro: manage_event(action=create, timezone=America/Sao_Paulo, add_google_meet=true, …)
      → "✅ Criado: <link do evento>"  (editar depois = manage_event action=update)
```

---

## 6. Segredos (Bitwarden-first)

**Regra:** **Bitwarden é a fonte da verdade**; segredos são injetados em runtime no `.env`
do `HERMES_HOME` (Linux/Hetzner: `~/.hermes/.env`, `chmod 600`; Windows: `%LOCALAPPDATA%/hermes`).
**Nunca** commitar; **nunca** no Obsidian.

| Credencial | Necessária p/ | Onde fica |
|---|---|---|
| **Google OAuth** (Gmail/Calendar pessoal) | MCP `user-google-tools` | gerido pelo próprio MCP (sem key no repo) |
| **2ª conta Google** (empresa) | leitura/ações empresa | **app password Google** (IMAP via Himalaya) **ou** 2º OAuth do MCP |
| **Hostinger pessoal — app password** | IMAP/SMTP | Bitwarden → Himalaya `config.toml` (`command`/keyring) ou `.env` |
| **Hostinger empresa — app password** | IMAP/SMTP | idem (item separado no Bitwarden) |
| **WhatsApp Baileys — pasta de sessão** | login WhatsApp | **é credencial**: `~/.hermes/platforms/whatsapp/session` (`chmod 700`), **nunca** commitar/compartilhar |
| **WhatsApp Cloud API** (se fase futura) | Phone Number ID, **token permanente** (System User), **App Secret** | Bitwarden |
| **GEMINI/GOOGLE API key** | modelo barato (triagem/resumo) | já no `.env` do Hermes |
| **OPENROUTER API key** | modelo barato + Claude via OpenRouter | já no `.env` |
| **ANTHROPIC API key** (opcional) | Claude direto (alternativa ao OpenRouter) | Bitwarden (se adotado) |

> Himalaya suporta senha via **comando** (`passwd.cmd = "bw get password <item>"`) → app
> password do Hostinger **não fica em texto plano** no `config.toml`.

---
## 7. Plano faseado

### Fase 0 — Pré-requisitos / decisões (sem código)
- Decidir **canal WhatsApp** (self-chat pessoal ✅ vs número dedicado).
- Gerar **app passwords Hostinger** (pessoal + empresa); confirmar Hostinger vs Titan.
- Definir **estratégia 2ª conta Google** (IMAP/Himalaya vs 2º OAuth).
- Definir **provider de raciocínio** (OpenRouter vs Anthropic key).
- Subir **gateway Hermes no Hetzner** como serviço; parear WhatsApp (QR).

### Fase 1 — MVP: **resumo diário read-only** no WhatsApp
- 1 cron (~07:30 BRT) → ingestão **só não-lidos/últimas N horas** de **1–2 contas**
  (Gmail pessoal via MCP + 1 Hostinger via Himalaya) → **triagem barata** → **digest** no
  WhatsApp pessoal. **Sem ações.**
- **Critério de sucesso:** digest útil + **custo de token medido** (`/usage`) dentro do alvo.

### Fase 2 — **Ações com confirmação**
- Resposta conversacional liga as ações: **lixeira/arquivar/marcar-lido** + **criar evento**,
  todas com **dry-run + `/approve`**; **delete permanente** só com dupla confirmação.
- Ligar **log de auditoria** + **undo** (untrash/re-label).

### Fase 3 — **Multi-conta completo + robustez**
- Adicionar **Gmail empresa** + **Hostinger empresa**; roteamento por conta no digest.
- NL mais rico ("responde X", rascunhos p/ revisão).
- (Opcional) migrar WhatsApp p/ **Cloud API** em número dedicado (template "utility" p/ o
  push diário) e/ou `watch_mailbox` (push) no lugar de polling.

### Lista mínima de DECISÕES / CREDENCIAIS para começar
1. **WhatsApp:** número **pessoal (self-chat)** ou **dedicado**? (define risco/Cloud API).
2. **Hostinger:** cada caixa é **Hostinger Email** ou **Titan**? → gerar **app password** p/
   **pessoal** e **empresa**.
3. **Google empresa:** é Gmail/Workspace? Quer **Calendar** nela (2º OAuth) ou **só e-mail**
   (IMAP/Himalaya)? → fornecer **app password Google** se IMAP.
4. **Provider de raciocínio (Claude):** **OpenRouter** (já tem key) ou **Anthropic API key**
   (nova, no Bitwarden)?
5. **Hetzner:** confirmar acesso SSH + rodar `gateway` como serviço.
6. **Janela do digest** (horário + fuso `America/Sao_Paulo`) e **quantas contas** no MVP.
7. **Política destrutiva:** confirmar **"lixeira por padrão; delete permanente só com dupla
   confirmação"**.

---

## Anexo A — Perguntas em aberto
- O runtime do Hermes permite **2 instâncias** do MCP `user-google-tools` (2 contas Google)?
  Se não, multi-conta Google = **IMAP/Himalaya**.
- Volume diário típico de e-mails (dimensiona cap/janela e custo).
- Quer **rascunho de resposta** (revisão) ou **envio direto** sob `/approve`?

## Anexo B — Referências (lidas/pesquisadas)
- MCP `user-google-tools`: `tools/{list_threads,get_message,modify_message,trash_message,
  delete_message,manage_event,move_event,get_events,list_calendars,...}.json`.
- Hermes: `messaging/whatsapp.md`, `messaging/whatsapp-cloud.md`, `messaging/email.md`,
  `messaging/index.md`, `skills/bundled/email/email-himalaya.md`,
  `docs/chronos-managed-cron-contract.md`, `cron/scheduler.py`, `tools/{openrouter_client,
  write_approval,slash_confirm,tirith_security,mcp_oauth_manager}.py`.
- Hostinger/Titan IMAP/SMTP + app password (suporte Hostinger/Titan).
- WhatsApp: docs Baileys/Evolution/WAHA (risco ToS/ban) e Meta Cloud API pricing/migração
  de número (BR, BRL, janela 24h, templates utility ≈ US$0,008).

