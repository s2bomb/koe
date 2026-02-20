from __future__ import annotations

from contextlib import suppress
from pathlib import Path
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
            "koe.main.capture_audio",
            return_value={"kind": "empty"},
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


def test_run_pipeline_captured_path_orders_notifications_and_cleans_artifact() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    artifact_path = Path("/tmp/captured.wav")

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch(
            "koe.main.transcribe_audio",
            return_value={"kind": "text", "text": "hello"},
            create=True,
        ),
        patch(
            "koe.main.insert_transcript_text",
            return_value={"ok": True, "value": None},
            create=True,
        ),
        patch("koe.main.remove_audio_artifact", create=True) as cleanup_mock,
        patch("koe.main.send_notification", create=True) as notify_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "success"

    kinds = [call.args[0] for call in notify_mock.call_args_list]
    assert kinds == ["recording_started", "processing", "completed"]
    cleanup_mock.assert_called_once_with(artifact_path)


def test_run_pipeline_cleanup_does_not_mask_downstream_handoff_error(tmp_path: Path) -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    artifact_path = tmp_path / "already-removed.wav"

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch(
            "koe.main.transcribe_audio",
            return_value={"kind": "text", "text": "hello"},
            create=True,
        ),
        patch(
            "koe.main.insert_transcript_text",
            return_value={
                "ok": False,
                "error": {
                    "category": "insertion",
                    "message": "clipboard restore failed: xclip exited with 1",
                    "transcript_text": "hello",
                },
            },
            create=True,
        ),
        patch("koe.main.remove_audio_artifact", create=True) as cleanup_mock,
        patch("koe.main.release_instance_lock", create=True) as release_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "error_insertion"

    cleanup_mock.assert_called_once_with(artifact_path)
    release_mock.assert_called_once_with(lock_handle)


def test_run_pipeline_transcription_empty_returns_no_speech() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    artifact_path = Path("/tmp/captured.wav")

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch("koe.main.transcribe_audio", return_value={"kind": "empty"}, create=True),
        patch("koe.main.remove_audio_artifact", create=True) as cleanup_mock,
        patch("koe.main.send_notification", create=True) as notify_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "no_speech"

    kinds = [call.args[0] for call in notify_mock.call_args_list]
    assert kinds == ["recording_started", "processing", "no_speech"]
    cleanup_mock.assert_called_once_with(artifact_path)


def test_run_pipeline_capture_empty_returns_no_speech() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch("koe.main.capture_audio", return_value={"kind": "empty"}, create=True),
        patch("koe.main.send_notification", create=True) as notify_mock,
        patch("koe.main.transcribe_audio", create=True) as transcribe_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "no_speech"

    kinds = [call.args[0] for call in notify_mock.call_args_list]
    assert kinds == ["recording_started", "no_speech"]
    transcribe_mock.assert_not_called()


def test_run_pipeline_capture_error_returns_error_audio_with_payload() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    audio_error = {"category": "audio", "message": "mic not found", "device": "default"}

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "error", "error": audio_error},
            create=True,
        ),
        patch("koe.main.send_notification", create=True) as notify_mock,
        patch("koe.main.transcribe_audio", create=True) as transcribe_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "error_audio"

    kinds = [call.args[0] for call in notify_mock.call_args_list]
    assert kinds == ["recording_started", "error_audio"]
    notify_mock.assert_any_call("error_audio", audio_error)
    transcribe_mock.assert_not_called()


def test_run_pipeline_transcription_error_returns_error_transcription() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    artifact_path = Path("/tmp/captured.wav")
    transcription_error = {
        "category": "transcription",
        "message": "CUDA not available: driver missing",
        "cuda_available": False,
    }

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch(
            "koe.main.transcribe_audio",
            return_value={"kind": "error", "error": transcription_error},
            create=True,
        ),
        patch("koe.main.remove_audio_artifact", create=True) as cleanup_mock,
        patch("koe.main.send_notification", create=True) as notify_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "error_transcription"

    notify_mock.assert_any_call("processing")
    notify_mock.assert_any_call("error_transcription", transcription_error)
    cleanup_mock.assert_called_once_with(artifact_path)


def test_run_pipeline_transcription_text_inserts_and_returns_success() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    artifact_path = Path("/tmp/captured.wav")

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch(
            "koe.main.transcribe_audio",
            return_value={"kind": "text", "text": "hello"},
            create=True,
        ),
        patch(
            "koe.main.insert_transcript_text",
            return_value={"ok": True, "value": None},
            create=True,
        ) as insert_mock,
        patch("koe.main.remove_audio_artifact", create=True) as cleanup_mock,
        patch("koe.main.send_notification", create=True) as notify_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "success"

    insert_mock.assert_called_once_with("hello", DEFAULT_CONFIG)
    notify_mock.assert_any_call("completed")
    cleanup_mock.assert_called_once_with(artifact_path)


@pytest.mark.parametrize(
    "transcription_result",
    [
        {"kind": "empty"},
        {
            "kind": "error",
            "error": {
                "category": "transcription",
                "message": "model load failed: missing file",
                "cuda_available": True,
            },
        },
        {"kind": "text", "text": "hello"},
    ],
)
def test_run_pipeline_transcription_cleanup_runs_on_all_outcomes(
    transcription_result: object,
) -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    artifact_path = Path("/tmp/captured.wav")

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch("koe.main.transcribe_audio", return_value=transcription_result, create=True),
        patch(
            "koe.main.insert_transcript_text",
            return_value={"ok": True, "value": None},
            create=True,
        ),
        patch("koe.main.remove_audio_artifact", create=True) as cleanup_mock,
    ):
        run_pipeline(DEFAULT_CONFIG)

    cleanup_mock.assert_called_once_with(artifact_path)


def test_run_pipeline_processing_notification_precedes_transcription_call() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    artifact_path = Path("/tmp/captured.wav")
    events: list[str] = []

    def _notify(kind: str, *_args: object) -> None:
        events.append(f"notify:{kind}")

    def _transcribe(_artifact_path: Path, _config: KoeConfig) -> object:
        events.append("transcribe")
        return {"kind": "empty"}

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch("koe.main.transcribe_audio", side_effect=_transcribe, create=True),
        patch(
            "koe.main.insert_transcript_text",
            return_value={"ok": True, "value": None},
            create=True,
        ),
        patch("koe.main.send_notification", side_effect=_notify, create=True),
        patch("koe.main.remove_audio_artifact", create=True),
    ):
        run_pipeline(DEFAULT_CONFIG)

    assert "notify:processing" in events
    assert "transcribe" in events
    assert events.index("notify:processing") < events.index("transcribe")


def test_run_pipeline_recording_notification_precedes_capture_call() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    events: list[str] = []

    def _notify(kind: str, *_args: object) -> None:
        events.append(f"notify:{kind}")

    def _capture(_config: KoeConfig) -> object:
        events.append("capture_audio")
        return {"kind": "empty"}

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch("koe.main.capture_audio", side_effect=_capture, create=True),
        patch("koe.main.send_notification", side_effect=_notify, create=True),
    ):
        run_pipeline(DEFAULT_CONFIG)

    assert "notify:recording_started" in events
    assert "capture_audio" in events
    assert events.index("notify:recording_started") < events.index("capture_audio")


def test_run_pipeline_text_branch_maps_insertion_error_to_notification_and_outcome() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    artifact_path = Path("/tmp/captured.wav")
    insertion_error = {
        "category": "insertion",
        "message": "clipboard restore failed: xclip exited with 1",
        "transcript_text": "hello",
    }

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch(
            "koe.main.transcribe_audio",
            return_value={"kind": "text", "text": "hello"},
            create=True,
        ),
        patch(
            "koe.main.insert_transcript_text",
            return_value={"ok": False, "error": insertion_error},
            create=True,
        ) as insert_mock,
        patch("koe.main.remove_audio_artifact", create=True) as cleanup_mock,
        patch("koe.main.send_notification", create=True) as notify_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "error_insertion"

    insert_mock.assert_called_once_with("hello", DEFAULT_CONFIG)
    notify_mock.assert_any_call("error_insertion", insertion_error)
    cleanup_mock.assert_called_once_with(artifact_path)


@pytest.mark.parametrize(
    "insertion_result",
    [
        {"ok": True, "value": None},
        {
            "ok": False,
            "error": {
                "category": "insertion",
                "message": "clipboard restore failed: xclip exited with 1",
                "transcript_text": "hello",
            },
        },
    ],
)
def test_run_pipeline_cleanup_order_is_artifact_then_lock_with_insertion_outcomes(
    insertion_result: object,
) -> None:
    lock_handle = cast("InstanceLockHandle", DEFAULT_CONFIG["lock_file_path"])
    artifact_path = Path("/tmp/captured.wav")
    events: list[str] = []

    def _cleanup(path: Path) -> None:
        assert path == artifact_path
        events.append("remove_audio_artifact")

    def _release(handle: InstanceLockHandle) -> None:
        assert handle == lock_handle
        events.append("release_instance_lock")

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch(
            "koe.main.transcribe_audio",
            return_value={"kind": "text", "text": "hello"},
            create=True,
        ),
        patch("koe.main.insert_transcript_text", return_value=insertion_result, create=True),
        patch("koe.main.remove_audio_artifact", side_effect=_cleanup, create=True),
        patch("koe.main.release_instance_lock", side_effect=_release, create=True),
        patch("koe.main.send_notification", create=True),
    ):
        run_pipeline(DEFAULT_CONFIG)

    assert events == ["remove_audio_artifact", "release_instance_lock"]


def test_run_pipeline_processing_precedes_transcription_and_insertion_follows_text_result() -> None:
    lock_handle = DEFAULT_CONFIG["lock_file_path"]
    artifact_path = Path("/tmp/captured.wav")
    events: list[str] = []

    def _notify(kind: str, *_args: object) -> None:
        events.append(f"notify:{kind}")

    def _transcribe(_artifact_path: Path, _config: KoeConfig) -> object:
        events.append("transcribe")
        return {"kind": "text", "text": "hello"}

    def _insert(transcript_text: str, config: KoeConfig) -> object:
        assert transcript_text == "hello"
        assert config == DEFAULT_CONFIG
        events.append("insert")
        return {"ok": True, "value": None}

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
            return_value={"ok": True, "value": {"window_id": 1, "title": "Editor"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch("koe.main.transcribe_audio", side_effect=_transcribe, create=True),
        patch("koe.main.insert_transcript_text", side_effect=_insert, create=True),
        patch("koe.main.send_notification", side_effect=_notify, create=True),
        patch("koe.main.remove_audio_artifact", create=True),
    ):
        run_pipeline(DEFAULT_CONFIG)

    assert events.index("notify:processing") < events.index("transcribe")
    assert events.index("transcribe") < events.index("insert")
