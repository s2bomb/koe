"""Desktop notification transport with non-raising behavior."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, assert_never

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


def _notification_payload(kind: NotificationKind, error: KoeError | None) -> tuple[str, str]:  # noqa: PLR0911
    match kind:
        case "recording_started":
            return ("Koe", "Recording…")
        case "processing":
            return ("Koe", "Processing…")
        case "completed":
            return ("Koe", "Transcription complete")
        case "no_speech":
            return ("Koe", "No speech detected")
        case "already_running":
            return (
                "Koe already running",
                _error_message(error, "Another Koe invocation is active."),
            )
        case "error_focus":
            return ("Koe focus required", _error_message(error, "No focused window is available."))
        case "error_dependency":
            return (
                "Koe dependency issue",
                _error_message(error, "A required dependency is missing."),
            )
        case "error_audio":
            return ("Koe audio error", _error_message(error, "Microphone capture failed."))
        case "error_transcription":
            return ("Koe transcription error", _error_message(error, "Transcription failed."))
        case "error_insertion":
            return ("Koe insertion error", _error_message(error, "Text insertion failed."))
        case _ as unreachable:
            assert_never(unreachable)


def _error_message(error: KoeError | None, fallback: str) -> str:
    if error is None:
        return fallback

    return error["message"]
