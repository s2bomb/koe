from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest

import koe.main as koe_main
from koe.config import DEFAULT_CONFIG
from koe.main import main, outcome_to_exit_code, run_pipeline

if TYPE_CHECKING:
    from koe.config import KoeConfig
    from koe.types import ExitCode, InstanceLockHandle, PipelineOutcome


def test_main_maps_unexpected_exception_to_exit_2() -> None:
    with (
        patch("koe.main.run_pipeline", side_effect=Exception("boom")),
        patch("sys.exit") as exit_mock,
    ):
        main()

    exit_mock.assert_called_once_with(2)


@pytest.mark.parametrize(
    ("missing_tool", "which_map", "config_override"),
    [
        (
            None,
            {
                "xdotool": "/usr/bin/xdotool",
                "xclip": "/usr/bin/xclip",
                "notify-send": "/usr/bin/notify-send",
            },
            {},
        ),
        (
            "xdotool",
            {"xdotool": None, "xclip": "/usr/bin/xclip", "notify-send": "/usr/bin/notify-send"},
            {},
        ),
        (
            "xclip",
            {"xdotool": "/usr/bin/xdotool", "xclip": None, "notify-send": "/usr/bin/notify-send"},
            {},
        ),
        (
            "notify-send",
            {"xdotool": "/usr/bin/xdotool", "xclip": "/usr/bin/xclip", "notify-send": None},
            {},
        ),
        (
            "cuda",
            {
                "xdotool": "/usr/bin/xdotool",
                "xclip": "/usr/bin/xclip",
                "notify-send": "/usr/bin/notify-send",
            },
            {"whisper_device": "cpu"},
        ),
    ],
)
def test_dependency_preflight_maps_required_startup_failures(
    missing_tool: str | None,
    which_map: dict[str, str | None],
    config_override: dict[str, object],
) -> None:
    dependency_preflight = koe_main.dependency_preflight
    config = cast("KoeConfig", {**DEFAULT_CONFIG, **config_override})

    def _which(tool: str) -> str | None:
        return which_map.get(tool)

    with patch(
        "koe.main.shutil.which",
        side_effect=_which,
        create=True,
    ):
        result = dependency_preflight(config)

    if missing_tool is None:
        assert result == {"ok": True, "value": None}
        return

    assert result["ok"] is False
    assert result["error"]["category"] == "dependency"
    if missing_tool == "cuda":
        assert result["error"]["missing_tool"] in {"cuda", "whisper_device"}
        return

    assert result["error"]["missing_tool"] == missing_tool


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("success", 0),
        ("already_running", 1),
        ("no_focus", 1),
        ("no_speech", 1),
        ("error_dependency", 1),
        ("error_audio", 1),
        ("error_transcription", 1),
        ("error_insertion", 1),
        ("error_unexpected", 2),
    ],
)
def test_outcome_to_exit_code_is_total(outcome: PipelineOutcome, expected: ExitCode) -> None:
    assert outcome_to_exit_code(outcome) == expected


def test_run_pipeline_short_circuits_on_preflight_dependency_error() -> None:
    dependency_error = {
        "category": "dependency",
        "message": "missing tool",
        "missing_tool": "xdotool",
    }

    with (
        patch(
            "koe.main.dependency_preflight",
            return_value={"ok": False, "error": dependency_error},
            create=True,
        ),
        patch("koe.main.acquire_instance_lock", create=True) as lock_mock,
        patch("koe.main.check_x11_context", create=True) as x11_mock,
        patch("koe.main.check_focused_window", create=True) as focus_mock,
        patch("koe.main.send_notification", create=True) as notify_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "error_dependency"

    notify_mock.assert_called_once_with("error_dependency", dependency_error)
    lock_mock.assert_not_called()
    x11_mock.assert_not_called()
    focus_mock.assert_not_called()


def test_run_pipeline_short_circuits_on_lock_contention() -> None:
    already_running_error = {
        "category": "already_running",
        "message": "another koe instance is active",
        "lock_file": "/tmp/koe.lock",
        "conflicting_pid": 4242,
    }

    with (
        patch(
            "koe.main.dependency_preflight", return_value={"ok": True, "value": None}, create=True
        ),
        patch(
            "koe.main.acquire_instance_lock",
            return_value={"ok": False, "error": already_running_error},
            create=True,
        ),
        patch("koe.main.check_x11_context", create=True) as x11_mock,
        patch("koe.main.check_focused_window", create=True) as focus_mock,
        patch("koe.main.send_notification", create=True) as notify_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "already_running"

    notify_mock.assert_called_once_with("already_running", already_running_error)
    x11_mock.assert_not_called()
    focus_mock.assert_not_called()


def test_run_pipeline_maps_focus_failure_to_no_focus_and_releases_lock() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    focus_error = {"category": "focus", "message": "no focused window"}

    with (
        patch(
            "koe.main.dependency_preflight", return_value={"ok": True, "value": None}, create=True
        ),
        patch(
            "koe.main.acquire_instance_lock",
            return_value={"ok": True, "value": lock_handle},
            create=True,
        ),
        patch("koe.main.check_x11_context", return_value={"ok": True, "value": None}, create=True),
        patch(
            "koe.main.check_focused_window",
            return_value={"ok": False, "error": focus_error},
            create=True,
        ),
        patch("koe.main.release_instance_lock", create=True) as release_mock,
        patch("koe.main.send_notification", create=True) as notify_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "no_focus"

    notify_mock.assert_called_once_with("error_focus", focus_error)
    release_mock.assert_called_once_with(lock_handle)


def test_run_pipeline_enforces_pre_record_stage_ordering() -> None:
    events: list[str] = []
    lock_handle = cast("InstanceLockHandle", DEFAULT_CONFIG["lock_file_path"])

    def _mark(name: str, result: object) -> object:
        events.append(name)
        return result

    def _preflight(_config: KoeConfig) -> object:
        return _mark("dependency_preflight", {"ok": True, "value": None})

    def _acquire(_config: KoeConfig) -> object:
        return _mark("acquire_instance_lock", {"ok": True, "value": lock_handle})

    def _x11_context() -> object:
        return _mark("check_x11_context", {"ok": True, "value": None})

    def _focused_window() -> object:
        return _mark(
            "check_focused_window",
            {"ok": True, "value": {"window_id": 1, "title": "Editor"}},
        )

    def _release(_handle: InstanceLockHandle) -> object:
        return _mark("release_instance_lock", None)

    with (
        patch(
            "koe.main.dependency_preflight",
            side_effect=_preflight,
            create=True,
        ),
        patch(
            "koe.main.acquire_instance_lock",
            side_effect=_acquire,
            create=True,
        ),
        patch(
            "koe.main.check_x11_context",
            side_effect=_x11_context,
            create=True,
        ),
        patch(
            "koe.main.check_focused_window",
            side_effect=_focused_window,
            create=True,
        ),
        patch(
            "koe.main.release_instance_lock",
            side_effect=_release,
            create=True,
        ),
        suppress(Exception),
    ):
        run_pipeline(DEFAULT_CONFIG)

    assert events[:4] == [
        "dependency_preflight",
        "acquire_instance_lock",
        "check_x11_context",
        "check_focused_window",
    ]
