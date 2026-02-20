"""Microphone capture and temporary WAV artefact lifecycle for Section 3."""

from __future__ import annotations

import importlib
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Event  # noqa: TC003 - used at runtime in function signatures
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

_MAX_RECORDING_SECONDS = 300


def capture_audio(config: KoeConfig, /, stop_event: Event | None = None) -> AudioCaptureResult:
    """Capture microphone audio until stop_event is set, then persist a WAV artefact.

    If stop_event is None, falls back to a fixed max-duration recording.
    The stop_event is set by the SIGUSR1 handler when the user presses the
    hotkey a second time. Recording stops immediately and captured audio
    is written to a temporary WAV file for transcription.
    """
    if stop_event is not None:
        return _capture_until_stopped(config, stop_event)
    return _capture_fixed(config)


def _capture_until_stopped(config: KoeConfig, stop_event: Event, /) -> AudioCaptureResult:  # noqa: PLR0911
    """Stream-record from microphone until stop_event is set."""
    try:
        sd = importlib.import_module("sounddevice")
        np = importlib.import_module("numpy")
    except ModuleNotFoundError as exc:
        return {"kind": "error", "error": _audio_error(f"missing package: {exc.name}", exc, None)}

    chunks: list[object] = []

    def _callback(indata: object, _frames: int, _time: object, _status: object) -> None:
        copy_method = getattr(indata, "copy", None)
        if callable(copy_method):
            chunks.append(copy_method())

    try:
        stream = sd.InputStream(
            samplerate=config["sample_rate"],
            channels=config["audio_channels"],
            dtype=config["audio_format"],
            callback=_callback,
        )
        with stream:
            stop_event.wait(timeout=_MAX_RECORDING_SECONDS)
    except Exception as error:
        return {"kind": "error", "error": _audio_error("microphone unavailable", error, None)}

    if len(chunks) == 0:
        return {"kind": "empty"}

    try:
        samples = np.concatenate(chunks, axis=0)
    except Exception as error:
        return {"kind": "error", "error": _audio_error("audio concatenation failed", error, None)}

    if _is_empty_capture(samples):
        return {"kind": "empty"}

    artifact_path = _allocate_artifact_path(config)
    try:
        soundfile.write(artifact_path, samples, config["sample_rate"])
    except Exception as error:
        remove_audio_artifact(AudioArtifactPath(artifact_path))
        return {"kind": "error", "error": _audio_error("wav write failed", error, None)}

    return {"kind": "captured", "artifact_path": AudioArtifactPath(artifact_path)}


def _capture_fixed(config: KoeConfig, /) -> AudioCaptureResult:
    """Fixed-duration recording fallback (max duration)."""
    try:
        capture_frames = config["sample_rate"] * _MAX_RECORDING_SECONDS
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
