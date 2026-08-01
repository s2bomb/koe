"""Session backend detection: which platform seam the pipeline dispatches to.

One place answers "where are we running" for every module that branches by
platform (insert, window, notify, main preflight). Detection order:

1. ``KOE_BACKEND`` env override — tests and manual forcing
2. ``sys.platform`` — darwin is a compile-time fact of the host
3. ``XDG_SESSION_TYPE``/``DISPLAY`` — wayland vs x11 within a linux session
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

type Backend = Literal["darwin", "wayland", "x11"]


def detect_backend() -> Backend:
    """Return the live session's backend."""
    return determine_backend(sys.platform, os.environ)


def determine_backend(platform: str, env: Mapping[str, str], /) -> Backend:
    """Pure backend decision from a platform string and an environment mapping."""
    override = env.get("KOE_BACKEND")
    if override == "darwin":
        return "darwin"
    if override == "wayland":
        return "wayland"
    if override == "x11":
        return "x11"

    if platform == "darwin":
        return "darwin"
    if env.get("XDG_SESSION_TYPE") == "wayland" and not env.get("DISPLAY"):
        return "wayland"
    return "x11"
