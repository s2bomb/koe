"""Clipboard-backed transcript insertion for Section 5."""

from __future__ import annotations

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
                "clipboard write failed:",
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
            ["xclip", "-selection", "clipboard", "-o"],
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
            ["xclip", "-selection", "clipboard", "-in"],
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
            ["xclip", "-selection", "clipboard", "-in"],
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
