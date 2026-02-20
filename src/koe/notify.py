"""Desktop notification transport with non-raising behavior."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from koe.types import KoeError, NotificationKind


def send_notification(kind: NotificationKind, error: KoeError | None = None) -> None:
    """Attempt to send a desktop notification and swallow transport failures."""
    title, message = _notification_payload(kind, error)
    try:
        subprocess.run(
            ["notify-send", title, message],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return


def _notification_payload(kind: NotificationKind, error: KoeError | None) -> tuple[str, str]:
    if kind == "already_running":
        return ("Koe already running", _error_message(error, "Another Koe invocation is active."))
    if kind == "error_focus":
        return ("Koe focus required", _error_message(error, "No focused window is available."))
    if kind == "error_dependency":
        return ("Koe dependency issue", _error_message(error, "A required dependency is missing."))

    return ("Koe", kind.replace("_", " "))


def _error_message(error: KoeError | None, fallback: str) -> str:
    if error is None:
        return fallback

    return error["message"]
