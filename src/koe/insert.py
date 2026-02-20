"""Clipboard-backed transcript insertion for Section 5."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from koe.config import KoeConfig
    from koe.types import ClipboardState, InsertionError, Result


def insert_transcript_text(
    transcript_text: str, config: KoeConfig, /
) -> Result[None, InsertionError]:
    """Insert transcript text via backup, write, paste, and restore."""
    if transcript_text.strip() == "":
        return {
            "ok": False,
            "error": _insertion_error(
                "insertion rejected:",
                "transcript text is empty",
                transcript_text,
            ),
        }

    backup_result = backup_clipboard_text(transcript_text)
    if backup_result["ok"] is False:
        return backup_result

    write_result = write_clipboard_text(transcript_text, transcript_text)
    if write_result["ok"] is False:
        return write_result

    paste_result = simulate_paste(config, transcript_text)
    if paste_result["ok"] is False:
        return paste_result

    restore_result = restore_clipboard_text(backup_result["value"], transcript_text)
    if restore_result["ok"] is False:
        return restore_result

    return {"ok": True, "value": None}


def backup_clipboard_text(transcript_text: str, /) -> Result[ClipboardState, InsertionError]:
    """Read text clipboard content before overwrite."""
    try:
        result = subprocess.run(
            _clipboard_read_command(),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {
            "ok": False,
            "error": _insertion_error(
                "clipboard backup failed:",
                str(exc),
                transcript_text,
            ),
        }

    if result.returncode == 0:
        return {"ok": True, "value": {"content": result.stdout}}

    stderr = result.stderr.strip().lower()
    if _is_non_text_clipboard(stderr):
        return {"ok": True, "value": {"content": None}}

    return {
        "ok": False,
        "error": _insertion_error(
            "clipboard backup failed:",
            result.stderr.strip() or f"xclip exited with {result.returncode}",
            transcript_text,
        ),
    }


def write_clipboard_text(text: str, transcript_text: str, /) -> Result[None, InsertionError]:
    """Write text to X11 clipboard selection."""
    try:
        result = subprocess.run(
            _clipboard_write_command(),
            check=False,
            capture_output=True,
            text=True,
            input=text,
        )
    except OSError as exc:
        return {
            "ok": False,
            "error": _insertion_error(
                "clipboard write failed:",
                str(exc),
                transcript_text,
            ),
        }

    if result.returncode != 0:
        return {
            "ok": False,
            "error": _insertion_error(
                "clipboard write failed:",
                result.stderr.strip() or f"xclip exited with {result.returncode}",
                transcript_text,
            ),
        }

    return {"ok": True, "value": None}


def simulate_paste(config: KoeConfig, transcript_text: str, /) -> Result[None, InsertionError]:
    """Paste clipboard content into the focused input."""
    if _is_wayland_session():
        return _simulate_wayland_paste(config, transcript_text)

    key_chord = f"{config['paste_key_modifier']}+{config['paste_key']}"
    try:
        result = subprocess.run(
            ["xdotool", "key", "--clearmodifiers", key_chord],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {
            "ok": False,
            "error": _insertion_error(
                "paste simulation failed:",
                str(exc),
                transcript_text,
            ),
        }

    if result.returncode != 0:
        return {
            "ok": False,
            "error": _insertion_error(
                "paste simulation failed:",
                result.stderr.strip() or f"xdotool exited with {result.returncode}",
                transcript_text,
            ),
        }

    return {"ok": True, "value": None}


def restore_clipboard_text(
    state: ClipboardState,
    transcript_text: str,
    /,
) -> Result[None, InsertionError]:
    """Restore prior text clipboard state after insertion."""
    previous_content = state["content"]
    if previous_content is None:
        return {"ok": True, "value": None}

    try:
        result = subprocess.run(
            _clipboard_write_command(),
            check=False,
            capture_output=True,
            text=True,
            input=previous_content,
        )
    except OSError as exc:
        return {
            "ok": False,
            "error": _insertion_error(
                "clipboard restore failed:",
                str(exc),
                transcript_text,
            ),
        }

    if result.returncode != 0:
        return {
            "ok": False,
            "error": _insertion_error(
                "clipboard restore failed:",
                result.stderr.strip() or f"xclip exited with {result.returncode}",
                transcript_text,
            ),
        }

    return {"ok": True, "value": None}


def _is_non_text_clipboard(stderr: str, /) -> bool:
    """Classify xclip output that indicates no readable text payload."""
    return (
        stderr == ""
        or "no text" in stderr
        or "target string not available" in stderr
        or "target text not available" in stderr
        or "target utf8_string not available" in stderr
    )


def _insertion_error(prefix: str, detail: str, transcript_text: str, /) -> InsertionError:
    """Create a normalized insertion error payload."""
    return {
        "category": "insertion",
        "message": f"{prefix} {detail}",
        "transcript_text": transcript_text,
    }


def _is_wayland_session() -> bool:
    backend_override = os.environ.get("KOE_BACKEND")
    if backend_override == "wayland":
        return True
    if backend_override == "x11":
        return False

    return os.environ.get("XDG_SESSION_TYPE") == "wayland" and not bool(os.environ.get("DISPLAY"))


def _clipboard_read_command() -> list[str]:
    if _is_wayland_session() and shutil.which("wl-paste") is not None:
        return ["wl-paste", "--no-newline"]
    return ["xclip", "-selection", "clipboard", "-o"]


def _clipboard_write_command() -> list[str]:
    if _is_wayland_session() and shutil.which("wl-copy") is not None:
        return ["wl-copy"]
    return ["xclip", "-selection", "clipboard", "-in"]


def _simulate_wayland_paste(
    config: KoeConfig, transcript_text: str, /
) -> Result[None, InsertionError]:
    if shutil.which("wtype") is not None:
        return _simulate_wtype_paste(config, transcript_text)
    return _simulate_hyprctl_paste(config, transcript_text)


def _simulate_wtype_paste(
    config: KoeConfig, transcript_text: str, /
) -> Result[None, InsertionError]:
    modifier_parts = [
        part.strip().lower() for part in config["paste_key_modifier"].split("+") if part
    ]
    command = ["wtype"]
    for modifier in modifier_parts:
        command.extend(["-M", modifier])
    command.extend(["-P", config["paste_key"].lower(), "-p", config["paste_key"].lower()])
    for modifier in reversed(modifier_parts):
        command.extend(["-m", modifier])

    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as exc:
        return {
            "ok": False,
            "error": _insertion_error("paste simulation failed:", str(exc), transcript_text),
        }

    if result.returncode != 0:
        return {
            "ok": False,
            "error": _insertion_error(
                "paste simulation failed:",
                result.stderr.strip() or f"wtype exited with {result.returncode}",
                transcript_text,
            ),
        }
    return {"ok": True, "value": None}


def _simulate_hyprctl_paste(
    config: KoeConfig, transcript_text: str, /
) -> Result[None, InsertionError]:
    modifier = config["paste_key_modifier"].upper().replace("+", " ")
    argument = f"{modifier}, {config['paste_key'].upper()},"
    try:
        result = subprocess.run(
            ["hyprctl", "dispatch", "sendshortcut", argument],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {
            "ok": False,
            "error": _insertion_error("paste simulation failed:", str(exc), transcript_text),
        }

    if result.returncode != 0:
        return {
            "ok": False,
            "error": _insertion_error(
                "paste simulation failed:",
                result.stderr.strip() or f"hyprctl exited with {result.returncode}",
                transcript_text,
            ),
        }

    return {"ok": True, "value": None}
