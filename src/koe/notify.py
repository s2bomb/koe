"""Desktop notification transport with non-raising behavior.

Per-backend transport: ``notify-send`` on linux, ``osascript`` on darwin.
osascript is chosen over UNUserNotificationCenter deliberately — the latter
requires a registered .app bundle and crashes from bare binaries, and the
legacy NSUserNotification API is dead on macOS 26 (mac-rig project 07, D7).
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, assert_never

from koe.backend import detect_backend

if TYPE_CHECKING:
    from koe.types import KoeError, NotificationKind

# Every pipeline state narrates itself through send_notification, so teeing it
# here gives a complete flight recorder: desktop banners can be suppressed by
# the OS (focus modes, unregistered identities), the file cannot.
_DIAGNOSTIC_LOG_PATH = Path("/tmp/koe.log")


def send_notification(kind: NotificationKind, error: KoeError | None = None) -> None:
    """Record the pipeline state to the log, then best-effort desktop banner."""
    title, message = _notification_payload(kind, error)
    _append_diagnostic_log(kind, message)
    try:
        subprocess.run(
            _notification_command(title, message),
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return


def _append_diagnostic_log(kind: NotificationKind, message: str, /) -> None:
    """Append one line to the flight-recorder log; never raise."""
    try:
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        with _DIAGNOSTIC_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {kind}: {message}\n")
    except Exception:
        return


def _notification_command(title: str, message: str) -> list[str]:
    if detect_backend() == "darwin":
        script = (
            f'display notification "{_escape_applescript(message)}"'
            f' with title "{_escape_applescript(title)}"'
        )
        return ["osascript", "-e", script]
    return ["notify-send", title, message]


def _escape_applescript(text: str) -> str:
    """Escape a python string for embedding in a double-quoted AppleScript literal."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


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

    if error["category"] == "insertion":
        transcript = error["transcript_text"].strip()
        if transcript == "":
            return error["message"]
        return f"{error['message']} Transcript: {transcript}"

    return error["message"]
