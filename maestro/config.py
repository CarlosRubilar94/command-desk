"""Typed Maestro configuration, loaded from env / ``<HERMES_HOME>/.env``.

All secrets are read from the environment — **never** hardcoded or committed.
The exact env var names are documented in ``maestro/README.md`` and mirrored in
``maestro/.env.example``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Mapping, Optional

from .env import get_bool, get_int, get_str, hermes_home, load_env
from .sources.imap_source import PROVIDER_HOSTS

# Default Gemini Flash model for cheap triage and REST base URL.
DEFAULT_TRIAGE_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_CLAUDE_BIN = "claude"
DEFAULT_TIMEZONE = "America/Sao_Paulo"


@dataclass
class ImapAccountConfig:
    account: str
    host: str
    port: int
    user: str
    password: str
    use_ssl: bool = True
    mailbox: str = "INBOX"
    provider: str = "hostinger"

    @property
    def is_complete(self) -> bool:
        return bool(self.host and self.user and self.password)


@dataclass
class GmailConfig:
    enabled: bool = False
    account: str = "gmail_pessoal"
    server_name: str = "user-google-tools"
    query: str = "is:unread newer_than:1d"


@dataclass
class MaestroConfig:
    # Ingestion window / caps (token economy)
    window_hours: int = 24
    max_emails: int = 40
    body_max_chars: int = 1200
    cache_ttl_days: int = 14

    # Scheduling
    timezone: str = DEFAULT_TIMEZONE
    digest_hour: int = 7

    # Triage (Gemini Flash)
    triage_model: str = DEFAULT_TRIAGE_MODEL
    gemini_base_url: str = DEFAULT_GEMINI_BASE_URL
    gemini_api_key: str = ""

    # Reasoning (Claude Code CLI subprocess)
    reasoning_enabled: bool = True
    claude_bin: str = DEFAULT_CLAUDE_BIN
    claude_args: List[str] = field(default_factory=lambda: ["-p"])
    claude_timeout: int = 120

    # Delivery (WhatsApp bridge self-chat)
    whatsapp_target: str = ""
    whatsapp_bridge_port: int = 3000

    # Preview / runtime
    preview_dir: str = ""
    home: Path = field(default_factory=hermes_home)

    # Phase 2 (disabled by default — read-only Phase 1)
    phase2_actions_enabled: bool = False

    # Accounts
    imap_accounts: List[ImapAccountConfig] = field(default_factory=list)
    gmail: GmailConfig = field(default_factory=GmailConfig)

    # ---- derived paths -------------------------------------------------
    @property
    def state_dir(self) -> Path:
        return self.home / "maestro"

    @property
    def seen_cache_path(self) -> Path:
        return self.state_dir / "seen.json"

    @property
    def preview_path_dir(self) -> Path:
        return Path(self.preview_dir) if self.preview_dir else (self.state_dir / "preview")

    @property
    def audit_log_path(self) -> Path:
        return self.home / "logs" / "maestro-audit.jsonl"

    def account_labels(self) -> List[str]:
        labels = [a.account for a in self.imap_accounts if a.is_complete]
        if self.gmail.enabled:
            labels.append(self.gmail.account)
        return labels

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "MaestroConfig":
        env = env or load_env()
        cfg = cls(
            window_hours=get_int(env, "MAESTRO_WINDOW_HOURS", 24),
            max_emails=get_int(env, "MAESTRO_MAX_EMAILS", 40),
            body_max_chars=get_int(env, "MAESTRO_BODY_MAX_CHARS", 1200),
            cache_ttl_days=get_int(env, "MAESTRO_CACHE_TTL_DAYS", 14),
            timezone=get_str(env, "MAESTRO_TIMEZONE", DEFAULT_TIMEZONE),
            digest_hour=get_int(env, "MAESTRO_DIGEST_HOUR", 7),
            triage_model=get_str(env, "MAESTRO_TRIAGE_MODEL", DEFAULT_TRIAGE_MODEL),
            gemini_base_url=get_str(env, "MAESTRO_GEMINI_BASE_URL", DEFAULT_GEMINI_BASE_URL).rstrip("/"),
            gemini_api_key=get_str(env, "GEMINI_API_KEY", "") or get_str(env, "GOOGLE_API_KEY", ""),
            reasoning_enabled=get_bool(env, "MAESTRO_REASONING_ENABLED", True),
            claude_bin=get_str(env, "MAESTRO_CLAUDE_BIN", DEFAULT_CLAUDE_BIN),
            claude_args=_split_args(get_str(env, "MAESTRO_CLAUDE_ARGS", "-p")),
            claude_timeout=get_int(env, "MAESTRO_CLAUDE_TIMEOUT", 120),
            whatsapp_target=get_str(env, "MAESTRO_WHATSAPP_TARGET", "")
            or get_str(env, "WHATSAPP_HOME_CHANNEL", ""),
            whatsapp_bridge_port=get_int(env, "MAESTRO_WHATSAPP_BRIDGE_PORT", 0)
            or get_int(env, "WHATSAPP_BRIDGE_PORT", 3000),
            preview_dir=get_str(env, "MAESTRO_PREVIEW_DIR", ""),
            phase2_actions_enabled=get_bool(env, "MAESTRO_PHASE2_ACTIONS_ENABLED", False),
        )
        cfg.imap_accounts = _load_imap_accounts(env)
        cfg.gmail = _load_gmail_config(env, cfg.window_hours)
        home_override = get_str(env, "HERMES_HOME", "")
        if home_override:
            cfg.home = Path(home_override).expanduser()
        return cfg


def _split_args(value: str) -> List[str]:
    import shlex

    try:
        parts = shlex.split(value)
    except ValueError:
        parts = value.split()
    return parts or ["-p"]


def _load_imap_accounts(env: Mapping[str, str]) -> List[ImapAccountConfig]:
    """Load IMAP accounts. The MVP ships the Hostinger 'empresa' account; extra
    accounts can be added by listing prefixes in ``MAESTRO_IMAP_EXTRA_ACCOUNTS``.
    """
    accounts: List[ImapAccountConfig] = []
    prefixes = [("MAESTRO_HOSTINGER_EMPRESA", "hostinger_empresa")]
    extra = get_str(env, "MAESTRO_IMAP_EXTRA_ACCOUNTS", "")
    for token in [t.strip() for t in extra.split(",") if t.strip()]:
        prefixes.append((f"MAESTRO_IMAP_{token.upper()}", token.lower()))

    for prefix, label in prefixes:
        user = get_str(env, f"{prefix}_USER", "")
        password = get_str(env, f"{prefix}_APP_PASSWORD", "")
        if not user and not password:
            continue  # account not configured — silently skip
        provider = get_str(env, f"{prefix}_PROVIDER", "hostinger").lower()
        host = get_str(env, f"{prefix}_HOST", "") or PROVIDER_HOSTS.get(provider, PROVIDER_HOSTS["hostinger"])
        accounts.append(
            ImapAccountConfig(
                account=get_str(env, f"{prefix}_LABEL", label),
                host=host,
                port=get_int(env, f"{prefix}_PORT", 993),
                user=user,
                password=password,
                use_ssl=get_bool(env, f"{prefix}_SSL", True),
                mailbox=get_str(env, f"{prefix}_MAILBOX", "INBOX"),
                provider=provider,
            )
        )
    return accounts


def _load_gmail_config(env: Mapping[str, str], window_hours: int) -> GmailConfig:
    default_query = f"is:unread newer_than:{max(1, window_hours // 24)}d"
    return GmailConfig(
        enabled=get_bool(env, "MAESTRO_GMAIL_PESSOAL_ENABLED", False),
        account=get_str(env, "MAESTRO_GMAIL_PESSOAL_LABEL", "gmail_pessoal"),
        server_name=get_str(env, "MAESTRO_GMAIL_MCP_SERVER", "user-google-tools"),
        query=get_str(env, "MAESTRO_GMAIL_QUERY", default_query),
    )
