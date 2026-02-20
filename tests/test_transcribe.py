from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import Mock, patch

import pytest

import koe.transcribe as transcribe_module
from koe.config import DEFAULT_CONFIG, KoeConfig
from koe.types import AudioArtifactPath


class _Segment:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModel:
    def __init__(self, segments: list[_Segment], *, error: Exception | None = None) -> None:
        self._segments = segments
        self._error = error

    def transcribe(self, _audio_path: Path) -> tuple[list[_Segment], object]:
        if self._error is not None:
            raise self._error
        return (self._segments, object())


class _GeneratorFailingModel:
    def transcribe(self, _audio_path: Path) -> tuple[object, object]:
        def _segments() -> object:
            raise RuntimeError("lazy decode failure")
            yield _Segment("unused")

        return (_segments(), object())


def _artifact_path() -> AudioArtifactPath:
    return AudioArtifactPath(Path("/tmp/sample.wav"))


def _config(**overrides: str) -> KoeConfig:
    return cast("KoeConfig", {**DEFAULT_CONFIG, **overrides})


def test_transcribe_audio_happy_path_returns_text_arm() -> None:
    fake_model = _FakeModel([_Segment("hello"), _Segment("world")])
    with patch("koe.transcribe.WhisperModel", return_value=fake_model, create=True):
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result["kind"] == "text"
    assert isinstance(result["text"], str)
    assert len(result["text"].strip()) > 0


def test_transcribe_audio_joins_segments_with_single_space_and_strips_boundaries() -> None:
    fake_model = _FakeModel([_Segment("  hello  "), _Segment(" world"), _Segment("  again ")])
    with patch("koe.transcribe.WhisperModel", return_value=fake_model, create=True):
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result == {"kind": "text", "text": "hello world again"}


def test_transcribe_audio_whitespace_only_returns_empty() -> None:
    fake_model = _FakeModel([_Segment("   "), _Segment("\n\t")])
    with patch("koe.transcribe.WhisperModel", return_value=fake_model, create=True):
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result == {"kind": "empty"}


@pytest.mark.parametrize(
    "token",
    [
        "[BLANK_AUDIO]",
        "[blank_audio]",
        "(background noise)",
        "(Background Noise)",
        "(silence)",
        "(Silence)",
        "[MUSIC]",
        "(music)",
        "(Music)",
        "(noise)",
        "(Noise)",
        "(beep)",
        "(Beep)",
        "[beep]",
        "[noise]",
        "[inaudible]",
        "(inaudible)",
        "(Inaudible)",
    ],
)
def test_transcribe_audio_noise_only_token_returns_empty(token: str) -> None:
    fake_model = _FakeModel([_Segment(token)])
    with patch("koe.transcribe.WhisperModel", return_value=fake_model, create=True):
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result == {"kind": "empty"}


def test_transcribe_audio_mixed_noise_and_speech_keeps_only_speech() -> None:
    fake_model = _FakeModel(
        [
            _Segment("(silence)"),
            _Segment("hello"),
            _Segment("[BLANK_AUDIO]"),
            _Segment("world"),
        ]
    )
    with patch("koe.transcribe.WhisperModel", return_value=fake_model, create=True):
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result == {"kind": "text", "text": "hello world"}


def test_transcribe_audio_cuda_unavailable_returns_typed_error() -> None:
    with patch(
        "koe.transcribe.WhisperModel",
        side_effect=RuntimeError("CUDA driver library not found"),
        create=True,
    ):
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result["kind"] == "error"
    assert result["error"]["category"] == "transcription"
    assert result["error"]["cuda_available"] is False
    assert result["error"]["message"].startswith("CUDA not available:")
    assert "CUDA driver library not found" in result["error"]["message"]


def test_transcribe_audio_model_load_failure_returns_typed_error() -> None:
    with patch(
        "koe.transcribe.WhisperModel",
        side_effect=RuntimeError("model cache corrupted"),
        create=True,
    ):
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result["kind"] == "error"
    assert result["error"]["category"] == "transcription"
    assert result["error"]["cuda_available"] is True
    assert result["error"]["message"].startswith("model load failed:")
    assert "model cache corrupted" in result["error"]["message"]


def test_transcribe_audio_inference_failure_returns_typed_error() -> None:
    fake_model = _FakeModel([], error=RuntimeError("kernel launch failed"))
    with patch("koe.transcribe.WhisperModel", return_value=fake_model, create=True):
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result["kind"] == "error"
    assert result["error"]["category"] == "transcription"
    assert result["error"]["cuda_available"] is True
    assert result["error"]["message"].startswith("inference failed:")
    assert "kernel launch failed" in result["error"]["message"]


def test_transcribe_audio_generator_failure_returns_typed_error() -> None:
    fake_model = _GeneratorFailingModel()
    with patch("koe.transcribe.WhisperModel", return_value=fake_model, create=True):
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result["kind"] == "error"
    assert result["error"]["category"] == "transcription"
    assert result["error"]["message"].startswith("inference failed:")
    assert "lazy decode failure" in result["error"]["message"]


@pytest.mark.parametrize(
    ("constructor_side_effect", "fake_model"),
    [
        (RuntimeError("cuda runtime unavailable"), None),
        (RuntimeError("weights missing"), None),
        (None, _FakeModel([], error=RuntimeError("decode failure"))),
    ],
)
def test_transcribe_audio_expected_failures_return_error_arm_without_raising(
    constructor_side_effect: Exception | None,
    fake_model: _FakeModel | None,
) -> None:
    if constructor_side_effect is not None:
        patcher = patch(
            "koe.transcribe.WhisperModel", side_effect=constructor_side_effect, create=True
        )
    else:
        patcher = patch("koe.transcribe.WhisperModel", return_value=fake_model, create=True)

    with patcher:
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result["kind"] == "error"


def test_transcribe_audio_constructs_model_with_cuda_config_values() -> None:
    config = _config(
        whisper_model="small.en",
        whisper_device="cuda",
        whisper_compute_type="int8_float16",
    )
    fake_model = _FakeModel([_Segment("hello")])
    constructor_mock = Mock(return_value=fake_model)

    with patch("koe.transcribe.WhisperModel", constructor_mock, create=True):
        result = transcribe_module.transcribe_audio(_artifact_path(), config)

    assert result["kind"] in {"text", "empty", "error"}
    assert constructor_mock.call_count == 1
    call_args = constructor_mock.call_args
    assert call_args is not None
    args = call_args.args
    kwargs = call_args.kwargs
    if args:
        assert args[0] == config["whisper_model"]
    else:
        assert kwargs.get("model_size_or_path") == config["whisper_model"]
    assert kwargs.get("device") == config["whisper_device"]
    assert kwargs.get("compute_type") == config["whisper_compute_type"]


def test_transcribe_audio_contract_result_shape_is_transcription_result() -> None:
    fake_model = _FakeModel([_Segment("hello")])
    with patch("koe.transcribe.WhisperModel", return_value=fake_model, create=True):
        result = transcribe_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert isinstance(result, dict)
    assert result["kind"] in {"text", "empty", "error"}
