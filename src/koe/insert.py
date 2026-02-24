"""Clipboard-backed transcript insertion."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from koe.config import KoeConfig
    from koe.types import InsertionError, Result


def insert_transcript_text(
    transcript_text: str, config: KoeConfig, /
) -> Result[None, InsertionError]:
    """Insert transcript text via write-then-paste stages."""
    if transcript_text.strip() == "":
        return {
            "ok": False,
            "error": _insertion_error(
                "insertion rejected:",
                "transcript text is empty",
                transcript_text,
            ),
        }

    write_result = write_clipboard_text(transcript_text, transcript_text)
    if write_result["ok"] is False:
        return write_result

    paste_result = simulate_paste(config, transcript_text)
    if paste_result["ok"] is False:
        return paste_result

    return {"ok": True, "value": None}


def write_clipboard_text(text: str, transcript_text: str, /) -> Result[None, InsertionError]:
    """Write text to clipboard selection.

    On Wayland, wl-copy forks a background process to serve clipboard requests,
    keeping stdout AND stderr open indefinitely. subprocess.run waits for all
    pipes to close, so any PIPE on either fd will hang. Both must be DEVNULL.
    We lose stderr error detail on Wayland but gain a non-hanging process.
    """
    is_wayland = _is_wayland_session()
    try:
        if is_wayland:
            result = subprocess.run(
                _clipboard_write_command(),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                input=text,
            )
        else:
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
        stderr_detail = "" if is_wayland else (result.stderr.strip() if result.stderr else "")
        tool_name = "wl-copy" if is_wayland else "xclip"
        return {
            "ok": False,
            "error": _insertion_error(
                "clipboard write failed:",
                stderr_detail or f"{tool_name} exited with {result.returncode}",
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


def _clipboard_write_command() -> list[str]:
    if _is_wayland_session() and shutil.which("wl-copy") is not None:
        return ["wl-copy"]
    return ["xclip", "-selection", "clipboard", "-in"]


def _simulate_wayland_paste(
    config: KoeConfig, transcript_text: str, /
) -> Result[None, InsertionError]:
    """Simulate paste on Wayland using Shift+Insert (Omarchy universal paste).

    Shift+Insert is the universal paste shortcut that works in both terminals
    and GUI applications, matching Omarchy's clipboard.conf binding for SUPER+V.
    """
    _ = config  # paste key config not used; Shift+Insert is universal
    try:
        result = subprocess.run(
            ["hyprctl", "dispatch", "sendshortcut", "SHIFT, Insert,"],
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
