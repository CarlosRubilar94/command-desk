"""Environment / config-file loading for Maestro.

Maestro must run both inside the Hermes runtime (as a cron ``no_agent`` script)
and standalone in unit tests, so this module deliberately avoids importing the
heavy ``hermes_cli.config`` module. It resolves ``HERMES_HOME`` the same way
Hermes does and parses the ``.env`` file there with a tiny stdlib-only parser.

Resolution order for a value:
    1. ``os.environ`` (real process env wins — matches python-dotenv default)
    2. ``<HERMES_HOME>/.env``

Nothing here ever logs secret *values*.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Mapping, Optional


def hermes_home() -> Path:
    """Return the Hermes home directory.

    Honours ``HERMES_HOME`` if set. Otherwise uses the platform default that
    Hermes itself uses: ``%LOCALAPPDATA%/hermes`` on Windows, ``~/.hermes``
    elsewhere. We try the real ``hermes_constants.get_hermes_home`` first (so we
    stay in lock-step with the runtime) and only fall back to our own logic when
    that import is unavailable (e.g. isolated unit tests).
    """
    explicit = os.environ.get("HERMES_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser()

    try:  # Prefer the canonical resolver when importable.
        from hermes_constants import get_hermes_home  # type: ignore

        return Path(get_hermes_home())
    except Exception:
        pass

    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if local:
            return Path(local) / "hermes"
        return Path.home() / "AppData" / "Local" / "hermes"
    return Path.home() / ".hermes"


def parse_dotenv(text: str) -> Dict[str, str]:
    """Parse ``.env`` text into a dict.

    Supports ``KEY=value``, ``export KEY=value``, ``#`` comments, blank lines,
    and single/double quoted values. Intentionally minimal — no interpolation.
    """
    out: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        out[key] = value
    return out


def load_env(home: Optional[Path] = None) -> Dict[str, str]:
    """Load merged environment: ``.env`` overlaid by ``os.environ``."""
    home = home or hermes_home()
    merged: Dict[str, str] = {}
    env_path = home / ".env"
    try:
        if env_path.is_file():
            merged.update(parse_dotenv(env_path.read_text(encoding="utf-8")))
    except OSError:
        pass
    # Real process environment always wins over the file.
    merged.update({k: v for k, v in os.environ.items() if v is not None})
    return merged


def get_bool(env: Mapping[str, str], key: str, default: bool = False) -> bool:
    raw = str(env.get(key, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "y"}


def get_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = str(env.get(key, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_str(env: Mapping[str, str], key: str, default: str = "") -> str:
    raw = env.get(key)
    if raw is None:
        return default
    raw = str(raw).strip()
    return raw if raw else default
