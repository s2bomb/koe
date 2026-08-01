"""Clipboard-backed transcript insertion.

Per-backend strategy (dispatch via koe.backend):

- darwin:  pbcopy, then a synthetic Cmd+V posted through CoreGraphics. The
  paste is best-effort by design — the clipboard is the delivery guarantee,
  the keystroke is a convenience (mac-rig project 07, decision D5).
- wayland: wl-copy, then hyprctl sendshortcut Shift+Insert.
- x11:     xclip, then xdotool Ctrl+V.
"""

from __future__ import annotations

import ctypes
import importlib
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Protocol, cast

from koe.backend import detect_backend

if TYPE_CHECKING:
    from koe.config import KoeConfig
    from koe.types import InsertionError, Result


class _QuartzLike(Protocol):
    """CoreGraphics surface used for the synthetic Cmd+V (pyobjc ships no full stubs)."""

    def CGPreflightPostEventAccess(self) -> bool: ...  # noqa: N802
    def CGRequestPostEventAccess(self) -> bool: ...  # noqa: N802
    def CGEventSourceCreate(self, state: int, /) -> object: ...  # noqa: N802
    def CGEventCreateKeyboardEvent(  # noqa: N802
        self, source: object, keycode: int, keydown: bool, /
    ) -> object: ...
    def CGEventSetFlags(self, event: object, flags: int, /) -> None: ...  # noqa: N802
    def CGEventPost(self, tap: int, event: object, /) -> None: ...  # noqa: N802


# Quartz exists only on macOS (pyobjc-framework-Quartz, darwin-marked dependency).
_quartz: _QuartzLike | None = (
    cast("_QuartzLike", importlib.import_module("Quartz")) if sys.platform == "darwin" else None
)

# ABI-frozen CoreGraphics enums (CGEventTypes.h / HIToolbox Events.h):
_KEY_V = 0x09  # kVK_ANSI_V
_EVENT_SOURCE_STATE_PRIVATE = -1  # kCGEventSourceStatePrivate: do not merge live
# hardware modifier state into the synthetic event — the user's hotkey chord is
# likely still physically held when we post.
_FLAG_MASK_COMMAND = 0x0010_0000  # kCGEventFlagMaskCommand
_SESSION_EVENT_TAP = 1  # kCGSessionEventTap: above hidutil remaps, which
# silently eat HID-level synthetic events.
_KEY_CHORD_GAP_SECONDS = 0.01


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
    pbcopy and xclip exit promptly, so they keep the captured-stderr path.
    """
    is_wayland = detect_backend() == "wayland"
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
        tool_name = _clipboard_write_command()[0]
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
    backend = detect_backend()
    if backend == "darwin":
        return _simulate_darwin_paste(transcript_text)
    if backend == "wayland":
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


def _clipboard_write_command() -> list[str]:
    backend = detect_backend()
    if backend == "darwin":
        return ["pbcopy"]
    if backend == "wayland":
        return ["wl-copy"]
    return ["xclip", "-selection", "clipboard", "-in"]


def _simulate_darwin_paste(transcript_text: str, /) -> Result[None, InsertionError]:
    """Post a synthetic Cmd+V through CoreGraphics, best-effort.

    Every known silent-failure mode is checked and reported as typed data:
    missing Quartz, secure input (a focused password field), and missing
    post-event permission (prompted for once via CGRequestPostEventAccess).
    A failure here never loses the transcript — it is already on the clipboard.
    """
    if _quartz is None:
        return {
            "ok": False,
            "error": _insertion_error(
                "paste simulation failed:", "Quartz is unavailable", transcript_text
            ),
        }

    if _secure_input_enabled():
        return {
            "ok": False,
            "error": _insertion_error(
                "paste simulation failed:",
                "secure input is active (a password field has focus); paste manually",
                transcript_text,
            ),
        }

    if not _quartz.CGPreflightPostEventAccess() and not _quartz.CGRequestPostEventAccess():
        return {
            "ok": False,
            "error": _insertion_error(
                "paste simulation failed:",
                "no post-event permission; grant koe Accessibility in System Settings",
                transcript_text,
            ),
        }

    try:
        source = _quartz.CGEventSourceCreate(_EVENT_SOURCE_STATE_PRIVATE)
        key_down = _quartz.CGEventCreateKeyboardEvent(source, _KEY_V, True)
        key_up = _quartz.CGEventCreateKeyboardEvent(source, _KEY_V, False)
        _quartz.CGEventSetFlags(key_down, _FLAG_MASK_COMMAND)
        _quartz.CGEventSetFlags(key_up, _FLAG_MASK_COMMAND)
        _quartz.CGEventPost(_SESSION_EVENT_TAP, key_down)
        time.sleep(_KEY_CHORD_GAP_SECONDS)
        _quartz.CGEventPost(_SESSION_EVENT_TAP, key_up)
    except Exception as exc:
        return {
            "ok": False,
            "error": _insertion_error("paste simulation failed:", str(exc), transcript_text),
        }

    return {"ok": True, "value": None}


def _secure_input_enabled() -> bool:
    """True when macOS secure input would silently swallow synthetic keystrokes."""
    try:
        carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        carbon.IsSecureEventInputEnabled.restype = ctypes.c_bool
        return bool(carbon.IsSecureEventInputEnabled())
    except OSError:
        return False


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
            ["hyprctl", "dispatch", "sendshortcut", "SHIFT,Insert,activewindow"],
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
