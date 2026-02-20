"""X11 context and focused-window lookups for Section 2."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from koe.types import DependencyError, FocusedWindow, FocusError, Result, WindowId


def check_x11_context() -> Result[None, DependencyError]:
    """Validate DISPLAY and xdotool availability before focus probing."""
    if _is_wayland_session():
        if shutil.which("hyprctl") is None:
            return {
                "ok": False,
                "error": {
                    "category": "dependency",
                    "message": "hyprctl is required on Wayland sessions",
                    "missing_tool": "hyprctl",
                },
            }
        return {"ok": True, "value": None}

    display = os.environ.get("DISPLAY")
    if not display:
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": "DISPLAY is not set",
                "missing_tool": "DISPLAY",
            },
        }

    if shutil.which("xdotool") is None:
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": "xdotool is required",
                "missing_tool": "xdotool",
            },
        }

    return {"ok": True, "value": None}


def check_focused_window() -> Result[FocusedWindow, FocusError]:  # noqa: PLR0911
    """Return focused window metadata or typed focus error."""
    x11_context = check_x11_context()
    if x11_context["ok"] is False:
        return {
            "ok": False,
            "error": {
                "category": "focus",
                "message": "focused window unavailable",
            },
        }

    if _is_wayland_session():
        return _check_wayland_focused_window()

    try:
        window_id_result = subprocess.run(
            ["xdotool", "getwindowfocus"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return {
            "ok": False,
            "error": {
                "category": "focus",
                "message": "failed to query focused window",
            },
        }

    if window_id_result.returncode != 0:
        return {
            "ok": False,
            "error": {
                "category": "focus",
                "message": "no focused window",
            },
        }

    window_id_text = window_id_result.stdout.strip()
    if not window_id_text:
        return {
            "ok": False,
            "error": {
                "category": "focus",
                "message": "no focused window",
            },
        }

    try:
        window_id = int(window_id_text)
    except ValueError:
        return {
            "ok": False,
            "error": {
                "category": "focus",
                "message": "invalid focused window id",
            },
        }

    title_result = subprocess.run(
        ["xdotool", "getwindowname", window_id_text],
        check=False,
        capture_output=True,
        text=True,
    )
    title = title_result.stdout.strip() if title_result.returncode == 0 else ""

    return {
        "ok": True,
        "value": {
            "window_id": WindowId(window_id),
            "title": title,
        },
    }


def _is_wayland_session() -> bool:
    backend_override = os.environ.get("KOE_BACKEND")
    if backend_override == "wayland":
        return True
    if backend_override == "x11":
        return False

    return os.environ.get("XDG_SESSION_TYPE") == "wayland" and not bool(os.environ.get("DISPLAY"))


def _check_wayland_focused_window() -> Result[FocusedWindow, FocusError]:
    try:
        active_window = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return {
            "ok": False,
            "error": {
                "category": "focus",
                "message": "failed to query focused window",
            },
        }

    if active_window.returncode != 0:
        return {
            "ok": False,
            "error": {
                "category": "focus",
                "message": "no focused window",
            },
        }

    try:
        payload = json.loads(active_window.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": {
                "category": "focus",
                "message": "invalid focused window payload",
            },
        }

    address = payload.get("address")
    if not isinstance(address, str) or not address.startswith("0x"):
        return {
            "ok": False,
            "error": {
                "category": "focus",
                "message": "no focused window",
            },
        }

    try:
        window_id = int(address, 16)
    except ValueError:
        return {
            "ok": False,
            "error": {
                "category": "focus",
                "message": "invalid focused window id",
            },
        }

    title = payload.get("title")
    if not isinstance(title, str):
        title = ""

    return {"ok": True, "value": {"window_id": WindowId(window_id), "title": title}}
