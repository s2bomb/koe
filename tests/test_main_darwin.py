from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest

import koe.main as main_module
from koe.config import DEFAULT_CONFIG
from koe.types import AudioArtifactPath

if TYPE_CHECKING:
    from koe.config import KoeConfig


@pytest.fixture(autouse=True)
def _pin_darwin_backend(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("KOE_BACKEND", "darwin")


def _config(**overrides: object) -> KoeConfig:
    return cast("KoeConfig", {**DEFAULT_CONFIG, **overrides})


def test_preflight_needs_no_external_tools_and_no_cuda() -> None:
    """No notify-send, no xdotool, no hyprctl, no CUDA gate — darwin has no tool probes."""
    with patch("shutil.which", return_value=None):
        result = main_module.dependency_preflight(DEFAULT_CONFIG)

    assert result == {"ok": True, "value": None}


def test_preflight_rejects_unwritable_temp_dir() -> None:
    config = _config(temp_dir=Path("/nonexistent-koe-temp"))

    result = main_module.dependency_preflight(config)

    assert result["ok"] is False
    assert result["error"]["missing_tool"] == "temp_dir"


def test_engine_dispatch_imports_darwin_engine() -> None:
    fake_engine_result = {"kind": "text", "text": "hi"}
    with patch.object(main_module.importlib, "import_module") as import_mock:
        import_mock.return_value.transcribe_audio.return_value = fake_engine_result
        result = main_module.transcribe_audio(AudioArtifactPath(Path("/tmp/a.wav")), DEFAULT_CONFIG)

    import_mock.assert_called_once_with("koe.transcribe_darwin")
    assert result == fake_engine_result


def test_engine_dispatch_imports_cuda_engine_on_x11(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOE_BACKEND", "x11")
    with patch.object(main_module.importlib, "import_module") as import_mock:
        import_mock.return_value.transcribe_audio.return_value = {"kind": "empty"}
        main_module.transcribe_audio(AudioArtifactPath(Path("/tmp/a.wav")), DEFAULT_CONFIG)

    import_mock.assert_called_once_with("koe.transcribe")


def test_preload_starts_thread_on_darwin_and_calls_engine() -> None:
    with patch.object(main_module.importlib, "import_module") as import_mock:
        thread = main_module._start_engine_preload(DEFAULT_CONFIG)  # pyright: ignore[reportPrivateUsage]
        assert thread is not None
        thread.join(timeout=5.0)

    import_mock.assert_called_once_with("koe.transcribe_darwin")
    import_mock.return_value.preload_model.assert_called_once_with(DEFAULT_CONFIG)


def test_preload_is_skipped_off_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOE_BACKEND", "x11")

    assert main_module._start_engine_preload(DEFAULT_CONFIG) is None  # pyright: ignore[reportPrivateUsage]


def test_recording_joins_preload_thread_before_returning() -> None:
    capture_result = {"kind": "empty"}

    class _FakeThread:
        def __init__(self) -> None:
            self.join_calls: list[float | None] = []

        def join(self, timeout: float | None = None) -> None:
            self.join_calls.append(timeout)

    fake_thread = _FakeThread()
    with (
        patch.object(main_module, "_start_engine_preload", return_value=fake_thread),
        patch.object(main_module, "capture_audio", return_value=capture_result, create=True),
        patch.object(main_module, "send_notification", create=True),
    ):
        result = main_module._record_with_engine_preload(DEFAULT_CONFIG)  # pyright: ignore[reportPrivateUsage]

    assert result == capture_result
    assert len(fake_thread.join_calls) == 1
    assert fake_thread.join_calls[0] is not None
