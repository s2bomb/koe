from __future__ import annotations

import os
import subprocess
from unittest.mock import patch

from koe import window

WINDOW_ID = 123


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["xdotool"],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def test_check_x11_context_returns_ok_when_display_and_tool_exist() -> None:
    with (
        patch.dict(os.environ, {"DISPLAY": ":1"}, clear=True),
        patch("shutil.which", return_value="/usr/bin/xdotool"),
    ):
        result = window.check_x11_context()

    assert result == {"ok": True, "value": None}


def test_check_x11_context_returns_dependency_error_when_missing_prerequisites() -> None:
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("shutil.which", return_value="/usr/bin/xdotool"),
    ):
        result = window.check_x11_context()

    assert result["ok"] is False
    assert result["error"]["category"] == "dependency"
    assert result["error"]["missing_tool"] == "DISPLAY"

    with (
        patch.dict(os.environ, {"DISPLAY": ":1"}, clear=True),
        patch("shutil.which", return_value=None),
    ):
        result = window.check_x11_context()

    assert result["ok"] is False
    assert result["error"]["category"] == "dependency"
    assert result["error"]["missing_tool"] == "xdotool"


def test_check_focused_window_returns_window_metadata_on_success() -> None:
    with (
        patch.dict(os.environ, {"DISPLAY": ":1"}, clear=True),
        patch("shutil.which", return_value="/usr/bin/xdotool"),
        patch("subprocess.run", side_effect=[_completed(f"{WINDOW_ID}\n"), _completed("Editor\n")]),
    ):
        result = window.check_focused_window()

    assert result["ok"] is True
    assert result["value"]["window_id"] == WINDOW_ID
    assert result["value"]["title"] == "Editor"


def test_check_focused_window_returns_focus_error_when_no_window_is_focused() -> None:
    with (
        patch.dict(os.environ, {"DISPLAY": ":1"}, clear=True),
        patch("shutil.which", return_value="/usr/bin/xdotool"),
        patch("subprocess.run", return_value=_completed("", returncode=1)),
    ):
        result = window.check_focused_window()

    assert result["ok"] is False
    assert result["error"]["category"] == "focus"
