"""X11 context and focused-window lookups for Section 2."""

from __future__ import annotations

import os
import shutil
import subprocess

from koe.types import DependencyError, FocusedWindow, FocusError, Result, WindowId


def check_x11_context() -> Result[None, DependencyError]:
    """Validate DISPLAY and xdotool availability before focus probing."""
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


def check_focused_window() -> Result[FocusedWindow, FocusError]:
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
