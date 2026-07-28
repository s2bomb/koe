"""Local Whisper transcription: CUDA-first with CPU fallback on VRAM contention."""

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
    from koe.types import AudioArtifactPath, Result, TranscriptionError, TranscriptionResult


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


# Fallback device. The config targets CUDA only (whisper_device: Literal["cuda"]);
# CPU is never a configured primary, only a degraded retry path.
_CPU_DEVICE: str = "cpu"

# Substrings (lowercased) in a CUDA load/inference failure that mean the GPU is
# present but out of VRAM — the case where a CPU retry is worth attempting.
_CUDA_OOM_INDICATORS: frozenset[str] = frozenset(
    {
        "out of memory",
        "cuda_error_out_of_memory",
        "cudaerrormemoryallocation",
        "failed to allocate",
        "cublas_status_alloc_failed",
        "cublas_status_not_initialized",
        "cudnn_status_alloc_failed",
    }
)

# Substrings (lowercased) that mean CUDA itself is missing/unusable on this host.
_CUDA_UNAVAILABLE_INDICATORS: tuple[str, ...] = (
    "not available",
    "unavailable",
    "not found",
    "driver",
)


class _SegmentLike(Protocol):
    text: str


class _WhisperModelLike(Protocol):
    def transcribe(self, audio_path: str, /) -> tuple[Iterable[_SegmentLike], object]: ...


def transcribe_audio(artifact_path: AudioArtifactPath, config: KoeConfig, /) -> TranscriptionResult:
    """Transcribe a WAV artifact into text, empty, or typed transcription error.

    Attempts the configured CUDA device first. If that attempt fails because CUDA
    is unavailable or out of VRAM (e.g. a game holds the GPU memory) and
    ``whisper_cpu_fallback`` is enabled, retries on CPU so transcription still
    succeeds. Failures unrelated to GPU availability are returned as-is without a
    pointless CPU retry.
    """
    primary = _attempt_transcription(
        artifact_path,
        config["whisper_model"],
        device=config["whisper_device"],
        compute_type=config["whisper_compute_type"],
    )
    if primary["kind"] != "error":
        return primary
    if not config["whisper_cpu_fallback"]:
        return primary
    if not _should_fall_back_to_cpu(primary["error"]):
        return primary

    fallback = _attempt_transcription(
        artifact_path,
        config["whisper_model"],
        device=_CPU_DEVICE,
        compute_type=config["whisper_cpu_compute_type"],
    )
    if fallback["kind"] != "error":
        return fallback
    return _both_devices_failed_error(primary["error"], fallback["error"])


def _attempt_transcription(
    artifact_path: AudioArtifactPath,
    model_name: str,
    /,
    *,
    device: str,
    compute_type: str,
) -> TranscriptionResult:
    """Load a model on one device and transcribe, shaping a typed result."""
    model_result = _load_model(model_name, device=device, compute_type=compute_type)
    if model_result["ok"] is False:
        return {"kind": "error", "error": model_result["error"]}
    return transcribe_audio_with_model(model_result["value"], artifact_path)


def load_transcription_model(config: KoeConfig, /) -> Result[_WhisperModelLike, TranscriptionError]:
    """Construct a reusable Whisper model instance on the configured CUDA device."""
    return _load_model(
        config["whisper_model"],
        device=config["whisper_device"],
        compute_type=config["whisper_compute_type"],
    )


def _load_model(
    model_name: str, /, *, device: str, compute_type: str
) -> Result[_WhisperModelLike, TranscriptionError]:
    """Construct a Whisper model on the requested device, classifying load failures."""
    try:
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
    except Exception as error:
        return {"ok": False, "error": _classify_load_error(error, device=device)}

    return {"ok": True, "value": cast("_WhisperModelLike", model)}


def transcribe_audio_with_model(
    model: _WhisperModelLike, artifact_path: AudioArtifactPath, /
) -> TranscriptionResult:
    """Transcribe a WAV artifact with an already-loaded Whisper model."""
    try:
        segments, _info = model.transcribe(str(artifact_path))
        normalized_text = _normalize_segments(segments)
    except Exception as error:
        return {
            "kind": "error",
            "error": _transcription_error(f"inference failed: {error}", cuda_available=True),
        }

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


def _classify_load_error(error: Exception, /, *, device: str) -> TranscriptionError:
    """Shape a model-load exception into a typed, human-readable transcription error."""
    message = str(error)
    lowered = message.lower()
    if device == _CPU_DEVICE:
        return _transcription_error(f"CPU model load failed: {message}", cuda_available=False)
    if _is_cuda_oom_message(lowered):
        return _transcription_error(
            f"CUDA out of memory (GPU VRAM in use elsewhere, e.g. a game): {message}",
            cuda_available=True,
        )
    if _is_cuda_unavailable_message(lowered):
        return _transcription_error(f"CUDA not available: {message}", cuda_available=False)
    return _transcription_error(f"model load failed: {message}", cuda_available=True)


def _should_fall_back_to_cpu(error: TranscriptionError, /) -> bool:
    """Decide whether a failed GPU attempt warrants a CPU retry.

    Only GPU-availability failures (CUDA missing, or out of VRAM) justify a retry.
    A corrupt model, bad compute type, or decode bug would fail identically on CPU.
    """
    message = error["message"].lower()
    return _is_cuda_oom_message(message) or _is_cuda_unavailable_message(message)


def _is_cuda_oom_message(message: str, /) -> bool:
    """True when a lowercased failure message indicates GPU VRAM exhaustion."""
    return any(indicator in message for indicator in _CUDA_OOM_INDICATORS)


def _is_cuda_unavailable_message(message: str, /) -> bool:
    """True when a lowercased failure message indicates CUDA itself is unusable."""
    if "cuda" not in message:
        return False
    return any(indicator in message for indicator in _CUDA_UNAVAILABLE_INDICATORS)


def _both_devices_failed_error(
    gpu_error: TranscriptionError, cpu_error: TranscriptionError, /
) -> TranscriptionResult:
    """Combine GPU and CPU failure diagnostics into one error result."""
    return {
        "kind": "error",
        "error": _transcription_error(
            f"GPU and CPU transcription both failed "
            f"(GPU: {gpu_error['message']}) (CPU: {cpu_error['message']})",
            cuda_available=False,
        ),
    }


def _transcription_error(message: str, *, cuda_available: bool) -> TranscriptionError:
    """Create a typed transcription error payload."""
    return {
        "category": "transcription",
        "message": message,
        "cuda_available": cuda_available,
    }
