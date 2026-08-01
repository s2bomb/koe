from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import numpy as np
import pytest

import koe.transcribe_darwin as transcribe_darwin_module
from koe.config import DEFAULT_CONFIG
from koe.types import AudioArtifactPath

if TYPE_CHECKING:
    from koe.types import TranscriptionResult

_MODEL_SAMPLE_RATE = 16_000


class _FakePreprocessArgs:
    def __init__(self, sample_rate: int) -> None:
        self.sample_rate = sample_rate


class _FakeAligned:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModel:
    def __init__(
        self,
        results: list[_FakeAligned],
        *,
        error: Exception | None = None,
        sample_rate: int = _MODEL_SAMPLE_RATE,
    ) -> None:
        self.preprocessor_config = _FakePreprocessArgs(sample_rate)
        self.generate_calls: list[object] = []
        self._results = results
        self._error = error

    def generate(self, mel: object, /) -> list[_FakeAligned]:
        self.generate_calls.append(mel)
        if self._error is not None:
            raise self._error
        return self._results


def _artifact_path() -> AudioArtifactPath:
    return AudioArtifactPath(Path("/tmp/sample.wav"))


def _mono_samples(seconds: float = 1.0) -> object:
    return np.zeros(int(_MODEL_SAMPLE_RATE * seconds), dtype=np.float32)


def _transcribe_with(
    model: _FakeModel,
    *,
    read_result: tuple[object, int] | None = None,
    read_error: Exception | None = None,
) -> TranscriptionResult:
    """Run transcribe_audio_with_model with soundfile and get_logmel patched out."""
    with (
        patch.object(transcribe_darwin_module, "soundfile") as fake_soundfile,
        patch.object(transcribe_darwin_module, "_parakeet_audio"),
    ):
        if read_error is not None:
            fake_soundfile.read.side_effect = read_error
        else:
            fake_soundfile.read.return_value = (
                read_result if read_result is not None else (_mono_samples(), _MODEL_SAMPLE_RATE)
            )
        return transcribe_darwin_module.transcribe_audio_with_model(model, _artifact_path())


def test_transcribe_with_model_happy_path_returns_text() -> None:
    model = _FakeModel([_FakeAligned("hello world")])

    result = _transcribe_with(model)

    assert result == {"kind": "text", "text": "hello world"}
    assert len(model.generate_calls) == 1


def test_transcribe_with_model_strips_surrounding_whitespace() -> None:
    model = _FakeModel([_FakeAligned("  padded text  ")])

    result = _transcribe_with(model)

    assert result == {"kind": "text", "text": "padded text"}


def test_transcribe_with_model_whitespace_only_text_is_empty_kind() -> None:
    model = _FakeModel([_FakeAligned("   ")])

    result = _transcribe_with(model)

    assert result == {"kind": "empty"}


def test_transcribe_with_model_no_results_is_empty_kind() -> None:
    model = _FakeModel([])

    result = _transcribe_with(model)

    assert result == {"kind": "empty"}


def test_transcribe_with_model_wav_read_failure_is_typed_error() -> None:
    model = _FakeModel([_FakeAligned("unused")])

    result = _transcribe_with(model, read_error=OSError("disk gone"))

    assert result["kind"] == "error"
    assert result["error"]["category"] == "transcription"
    assert "wav read failed" in result["error"]["message"]
    assert len(model.generate_calls) == 0


def test_transcribe_with_model_sample_rate_mismatch_is_typed_error() -> None:
    model = _FakeModel([_FakeAligned("unused")])

    result = _transcribe_with(model, read_result=(_mono_samples(), 44_100))

    assert result["kind"] == "error"
    assert "44100" in result["error"]["message"]
    assert "16000" in result["error"]["message"]
    assert len(model.generate_calls) == 0


def test_transcribe_with_model_multichannel_artifact_is_typed_error() -> None:
    model = _FakeModel([_FakeAligned("unused")])
    stereo = np.zeros((_MODEL_SAMPLE_RATE, 2), dtype=np.float32)

    result = _transcribe_with(model, read_result=(stereo, _MODEL_SAMPLE_RATE))

    assert result["kind"] == "error"
    assert "mono" in result["error"]["message"]
    assert len(model.generate_calls) == 0


def test_transcribe_with_model_inference_failure_is_typed_error() -> None:
    model = _FakeModel([], error=RuntimeError("metal exploded"))

    result = _transcribe_with(model)

    assert result["kind"] == "error"
    assert "inference failed: metal exploded" in result["error"]["message"]
    assert result["error"]["cuda_available"] is False


def test_load_transcription_model_failure_is_typed_error() -> None:
    with patch.object(transcribe_darwin_module, "_parakeet") as fake_parakeet:
        fake_parakeet.from_pretrained.side_effect = RuntimeError("no network")
        result = transcribe_darwin_module.load_transcription_model(DEFAULT_CONFIG)

    assert result["ok"] is False
    assert "model load failed: no network" in result["error"]["message"]


def test_load_transcription_model_passes_configured_model_id() -> None:
    sentinel_model = _FakeModel([])
    with patch.object(transcribe_darwin_module, "_parakeet") as fake_parakeet:
        fake_parakeet.from_pretrained.return_value = sentinel_model
        result = transcribe_darwin_module.load_transcription_model(DEFAULT_CONFIG)

    assert result["ok"] is True
    assert result["value"] is sentinel_model
    fake_parakeet.from_pretrained.assert_called_once_with(DEFAULT_CONFIG["parakeet_model"])


def test_transcribe_audio_composes_load_failure_into_error_result() -> None:
    with patch.object(transcribe_darwin_module, "_parakeet") as fake_parakeet:
        fake_parakeet.from_pretrained.side_effect = RuntimeError("offline")
        result = transcribe_darwin_module.transcribe_audio(_artifact_path(), DEFAULT_CONFIG)

    assert result["kind"] == "error"


def test_warm_up_model_runs_one_generate() -> None:
    model = _FakeModel([_FakeAligned("")])

    with patch.object(transcribe_darwin_module, "_parakeet_audio"):
        transcribe_darwin_module.warm_up_model(model)

    assert len(model.generate_calls) == 1


def test_warm_up_model_swallows_failures() -> None:
    model = _FakeModel([], error=RuntimeError("compile failed"))

    with patch.object(transcribe_darwin_module, "_parakeet_audio"):
        transcribe_darwin_module.warm_up_model(model)


_MODEL_CACHE_DIR = (
    Path.home() / ".cache" / "huggingface" / "hub" / "models--mlx-community--parakeet-tdt-0.6b-v3"
)


@pytest.mark.skipif(sys.platform != "darwin", reason="darwin engine integration")
@pytest.mark.skipif(not _MODEL_CACHE_DIR.exists(), reason="parakeet model not in HF cache")
def test_integration_real_model_transcribes_synthesized_speech(tmp_path: Path) -> None:
    """End-to-end proof on real Metal: say-synthesized speech in, correct words out."""
    aiff_path = tmp_path / "fixture.aiff"
    wav_path = tmp_path / "fixture.wav"
    subprocess.run(
        ["say", "-o", str(aiff_path), "The quick brown fox jumps over the lazy dog."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff_path), str(wav_path)],
        check=True,
        capture_output=True,
    )

    result = transcribe_darwin_module.transcribe_audio(AudioArtifactPath(wav_path), DEFAULT_CONFIG)

    assert result["kind"] == "text"
    assert "quick brown fox" in result["text"].lower()
