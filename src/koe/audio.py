"""Microphone capture and temporary WAV artefact lifecycle for Section 3."""

from __future__ import annotations

import importlib
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Protocol, cast

from koe.types import AudioArtifactPath, AudioCaptureResult, AudioError

if TYPE_CHECKING:
    from koe.config import KoeConfig


class _SoundDeviceLike(Protocol):
    def rec(self, frames: int, *, samplerate: int, channels: int, dtype: str) -> object: ...

    def wait(self) -> None: ...


class _SoundFileLike(Protocol):
    def write(self, file: Path, data: object, samplerate: int, /) -> None: ...


class _SoundDeviceFallback:
    def rec(self, frames: int, *, samplerate: int, channels: int, dtype: str) -> object:
        _ = (frames, samplerate, channels, dtype)
        raise RuntimeError("sounddevice is unavailable")

    def wait(self) -> None:
        raise RuntimeError("sounddevice is unavailable")


class _SoundFileFallback:
    def write(self, file: Path, data: object, samplerate: int, /) -> None:
        _ = (file, data, samplerate)
        raise RuntimeError("soundfile is unavailable")


def _load_sounddevice() -> _SoundDeviceLike:
    try:
        module = importlib.import_module("sounddevice")
    except ModuleNotFoundError:
        return _SoundDeviceFallback()

    return cast("_SoundDeviceLike", module)


def _load_soundfile() -> _SoundFileLike:
    try:
        module = importlib.import_module("soundfile")
    except ModuleNotFoundError:
        return _SoundFileFallback()

    return cast("_SoundFileLike", module)


sounddevice = _load_sounddevice()
soundfile = _load_soundfile()

_CAPTURE_SECONDS = 8


def capture_audio(config: KoeConfig, /) -> AudioCaptureResult:
    """Capture microphone audio and persist a temporary WAV artefact."""
    try:
        capture_frames = config["sample_rate"] * _CAPTURE_SECONDS
        samples = sounddevice.rec(
            frames=capture_frames,
            samplerate=config["sample_rate"],
            channels=config["audio_channels"],
            dtype=config["audio_format"],
        )
        sounddevice.wait()
    except Exception as error:
        return {"kind": "error", "error": _audio_error("microphone unavailable", error, None)}

    if _is_empty_capture(samples):
        return {"kind": "empty"}

    artifact_path = _allocate_artifact_path(config)
    try:
        soundfile.write(artifact_path, samples, config["sample_rate"])
    except Exception as error:
        remove_audio_artifact(AudioArtifactPath(artifact_path))
        return {"kind": "error", "error": _audio_error("wav write failed", error, None)}

    return {"kind": "captured", "artifact_path": AudioArtifactPath(artifact_path)}


def remove_audio_artifact(artifact_path: AudioArtifactPath, /) -> None:
    """Best-effort removal of a temporary WAV artefact without raising."""
    try:
        Path(artifact_path).unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _allocate_artifact_path(config: KoeConfig) -> Path:
    with NamedTemporaryFile(dir=config["temp_dir"], suffix=".wav", delete=False) as handle:
        return Path(handle.name)


def _audio_error(prefix: str, error: Exception, device: str | None) -> AudioError:
    return {
        "category": "audio",
        "message": f"{prefix}: {error}",
        "device": device,
    }


def _is_empty_capture(samples: object) -> bool:
    if isinstance(samples, str | bytes | bytearray):
        return len(samples) == 0

    if isinstance(samples, list | tuple):
        sequence = cast("list[object] | tuple[object, ...]", samples)
        return len(sequence) == 0

    size = getattr(samples, "size", None)
    if isinstance(size, int):
        return size == 0

    shape = getattr(samples, "shape", None)
    if isinstance(shape, tuple):
        shape_values = cast("tuple[object, ...]", shape)
        if len(shape_values) == 0:
            return True
        first = shape_values[0]
        if isinstance(first, int):
            return first == 0

    return False
