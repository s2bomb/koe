"""Local CUDA Whisper transcription result shaping for Section 4."""

from __future__ import annotations

import ctypes
import site
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast


def _preload_cuda_libraries() -> None:
    """Pre-load pip-installed nvidia CUDA libraries into the process global symbol table.

    LD_LIBRARY_PATH is read at process startup and cannot be modified at runtime.
    Instead, use ctypes.CDLL with RTLD_GLOBAL to make the shared libraries available
    before CTranslate2 (via faster-whisper) tries to link against them.
    """
    packages = site.getsitepackages()
    if not packages:
        return
    nvidia_dir = Path(packages[0]) / "nvidia"
    if not nvidia_dir.is_dir():
        return

    targets = ["libcublas.so.12", "libcublasLt.so.12", "libcudnn.so.9"]
    for target in targets:
        matches = list(nvidia_dir.rglob(target))
        for match in matches:
            try:
                ctypes.CDLL(str(match), mode=ctypes.RTLD_GLOBAL)
            except OSError:
                continue


_preload_cuda_libraries()

from faster_whisper import WhisperModel  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Iterable

    from koe.config import KoeConfig
    from koe.types import AudioArtifactPath, TranscriptionError, TranscriptionResult


_NOISE_TOKENS: frozenset[str] = frozenset(
    {
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
    }
)


class _SegmentLike(Protocol):
    text: str


def transcribe_audio(artifact_path: AudioArtifactPath, config: KoeConfig, /) -> TranscriptionResult:
    """Transcribe a WAV artifact into text, empty, or typed transcription error."""
    try:
        model = WhisperModel(
            config["whisper_model"],
            device=config["whisper_device"],
            compute_type=config["whisper_compute_type"],
        )
    except Exception as error:
        if _is_cuda_unavailable_error(error):
            return _transcription_error(f"CUDA not available: {error}", cuda_available=False)
        return _transcription_error(f"model load failed: {error}", cuda_available=True)

    try:
        segments, _info = model.transcribe(str(artifact_path))
        normalized_text = _normalize_segments(cast("Iterable[_SegmentLike]", segments))
    except Exception as error:
        return _transcription_error(f"inference failed: {error}", cuda_available=True)

    if normalized_text == "":
        return {"kind": "empty"}
    return {"kind": "text", "text": normalized_text}


def _normalize_segments(segments: Iterable[_SegmentLike], /) -> str:
    """Normalize and filter raw model segment text into insertion-ready output."""
    normalized_segments: list[str] = []
    for segment in segments:
        segment_text = segment.text.strip()
        if segment_text == "" or segment_text in _NOISE_TOKENS:
            continue
        normalized_segments.append(segment_text)
    return " ".join(normalized_segments).strip()


def _is_cuda_unavailable_error(error: Exception, /) -> bool:
    """Classify load-time exceptions that indicate CUDA is unavailable."""
    message = str(error).lower()
    if "cuda" not in message:
        return False
    indicators = ("not available", "unavailable", "not found", "driver")
    return any(indicator in message for indicator in indicators)


def _transcription_error(message: str, *, cuda_available: bool) -> TranscriptionResult:
    """Create a typed transcription failure result."""
    error: TranscriptionError = {
        "category": "transcription",
        "message": message,
        "cuda_available": cuda_available,
    }
    return {"kind": "error", "error": error}
