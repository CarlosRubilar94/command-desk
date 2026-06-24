"""Safe subprocess wrappers for text decoding.

Centralizes the utf-8 + replacement decoding policy so subprocess readers
cannot crash on locale-specific bytes during gateway/update flows.
"""

from __future__ import annotations

import subprocess
from typing import Any


_TEXT_KWARGS: dict[str, Any] = {
    "text": True,
    "encoding": "utf-8",
    "errors": "replace",
}


def safe_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Run ``cmd`` with safe text decoding by default."""

    merged = {**_TEXT_KWARGS, **kwargs}
    return subprocess.run(cmd, **merged)


def safe_popen(cmd: list[str], **kwargs: Any) -> subprocess.Popen:
    """Popen wrapper that decodes child output safely."""

    merged = {**_TEXT_KWARGS, **kwargs}
    return subprocess.Popen(cmd, **merged)
