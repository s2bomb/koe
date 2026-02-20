from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import patch

from koe.audio import capture_audio, remove_audio_artifact
from koe.config import DEFAULT_CONFIG, KoeConfig
from koe.types import AudioArtifactPath


def _audio_config(temp_dir: Path) -> KoeConfig:
    return cast("KoeConfig", {**DEFAULT_CONFIG, "temp_dir": temp_dir})


def test_capture_audio_returns_captured_artifact_on_happy_path(tmp_path: Path) -> None:
    config = _audio_config(tmp_path)
    fake_samples = [[0.5], [0.25]]

    with (
        patch("koe.audio.sounddevice.rec", return_value=fake_samples, create=True) as rec_mock,
        patch("koe.audio.sounddevice.wait", create=True),
        patch("koe.audio.soundfile.write", create=True) as write_mock,
    ):
        result = capture_audio(config)

    assert result["kind"] == "captured"
    assert Path(result["artifact_path"]).parent == tmp_path
    assert rec_mock.call_count == 1
    rec_kwargs = rec_mock.call_args.kwargs
    assert rec_kwargs.get("samplerate") == config["sample_rate"]
    assert rec_kwargs.get("frames") == config["sample_rate"] * 8
    assert rec_kwargs.get("channels") == config["audio_channels"]
    assert rec_kwargs.get("dtype") == config["audio_format"]
    assert write_mock.call_count == 1


def test_capture_audio_routes_zero_length_capture_to_empty(tmp_path: Path) -> None:
    config = _audio_config(tmp_path)

    with (
        patch("koe.audio.sounddevice.rec", return_value=[], create=True),
        patch("koe.audio.sounddevice.wait", create=True),
        patch("koe.audio.soundfile.write", create=True) as write_mock,
    ):
        result = capture_audio(config)

    assert result == {"kind": "empty"}
    write_mock.assert_not_called()


def test_capture_audio_maps_microphone_unavailable_to_audio_error(tmp_path: Path) -> None:
    config = _audio_config(tmp_path)

    with patch(
        "koe.audio.sounddevice.rec",
        side_effect=RuntimeError("no input device"),
        create=True,
    ):
        result = capture_audio(config)

    assert result["kind"] == "error"
    assert result["error"]["category"] == "audio"
    assert result["error"]["message"].startswith("microphone unavailable:")
    assert result["error"]["device"] is None


def test_capture_audio_maps_wav_write_failure_to_audio_error_and_cleans_tmp_path(
    tmp_path: Path,
) -> None:
    config = _audio_config(tmp_path)
    fake_samples = [[0.5], [0.25]]

    with (
        patch("koe.audio.sounddevice.rec", return_value=fake_samples, create=True),
        patch("koe.audio.sounddevice.wait", create=True),
        patch("koe.audio.soundfile.write", side_effect=OSError("disk full"), create=True),
    ):
        result = capture_audio(config)

    assert result["kind"] == "error"
    assert result["error"]["category"] == "audio"
    assert result["error"]["message"].startswith("wav write failed:")
    assert result["error"]["device"] is None
    assert list(tmp_path.iterdir()) == []


def test_remove_audio_artifact_deletes_existing_file(tmp_path: Path) -> None:
    artifact = tmp_path / "capture.wav"
    artifact.write_bytes(b"wav")

    outcome = remove_audio_artifact(AudioArtifactPath(artifact))

    assert outcome is None
    assert not artifact.exists()


def test_remove_audio_artifact_is_safe_for_missing_file(tmp_path: Path) -> None:
    artifact = AudioArtifactPath(tmp_path / "missing.wav")

    assert remove_audio_artifact(artifact) is None
    assert remove_audio_artifact(artifact) is None
