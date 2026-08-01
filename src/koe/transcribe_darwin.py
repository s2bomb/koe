"""Local Parakeet transcription for macOS: Metal inference via MLX, zero subprocesses.

The darwin engine seam. Mirrors the public surface of ``transcribe.py`` (the CUDA
engine) so the pipeline can dispatch by platform without caring which engine runs:

    transcribe_audio(artifact_path, config)           -> TranscriptionResult
    load_transcription_model(config)                  -> Result[model, TranscriptionError]
    transcribe_audio_with_model(model, artifact_path) -> TranscriptionResult
    warm_up_model(model)                              -> None (darwin extra)

Why not parakeet_mlx's own ``model.transcribe(path)``: it shells out to ffmpeg on
every call to support arbitrary input formats. Koe reads exactly one format — the
16 kHz mono float32 WAV koe itself wrote moments earlier — which soundfile
(already a koe dependency) decodes in-process in ~1 ms. No ffmpeg, no subprocess.

mlx/parakeet ship incomplete type stubs, so — like ``audio.py`` does for
sounddevice — the libraries are touched only through Protocol-typed handles and
their tensor values stay opaque ``object``s inside this module.

No noise-token filtering here: the Parakeet transducer emits nothing on silence,
unlike Whisper's encoder-decoder which hallucinates bracket tokens like
``[BLANK_AUDIO]`` that ``transcribe.py`` must scrub.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Protocol, cast

import numpy as np
import soundfile

if TYPE_CHECKING:
    from collections.abc import Sequence

    from koe.config import KoeConfig
    from koe.types import AudioArtifactPath, Result, TranscriptionError, TranscriptionResult


class _AlignedResultLike(Protocol):
    text: str


class _PreprocessArgsLike(Protocol):
    sample_rate: int


class _ParakeetModelLike(Protocol):
    @property
    def preprocessor_config(self) -> _PreprocessArgsLike: ...

    def generate(self, mel: object, /) -> Sequence[_AlignedResultLike]: ...

    def parameters(self) -> object: ...


class _ParakeetLoaderLike(Protocol):
    def from_pretrained(self, hf_id_or_path: str, /) -> object: ...


class _ParakeetAudioLike(Protocol):
    def get_logmel(self, samples: object, preprocess_args: object, /) -> object: ...


class _MlxCoreLike(Protocol):
    def array(self, samples: object, /) -> object: ...

    def eval(self, outputs: object, /) -> None: ...

    def synchronize(self) -> None: ...


class _SamplesLike(Protocol):
    @property
    def ndim(self) -> int: ...


_parakeet = cast("_ParakeetLoaderLike", importlib.import_module("parakeet_mlx"))
_parakeet_audio = cast("_ParakeetAudioLike", importlib.import_module("parakeet_mlx.audio"))
_mx = cast("_MlxCoreLike", importlib.import_module("mlx.core"))

# Model slot filled by preload_model() on a background thread while recording is
# in progress, so the stop-press pays neither the ~1.2 s model load nor the
# ~1 s first-generate Metal kernel compilation. Published only AFTER warm-up
# completes; a single attribute assignment, read once by the main thread after
# it joins the preload thread. (Platform-layer module global, koe's one
# explicit-state exception per module — same doctrine as the lockfile.)
_preloaded_model: _ParakeetModelLike | None = None


def preload_model(config: KoeConfig, /) -> None:
    """Load and warm the model, then publish it for take_preloaded_model().

    Runs on a background thread during recording. Failures leave the slot
    empty — transcribe_audio() then simply loads cold and reports any real
    fault as typed data on the main path.
    """
    global _preloaded_model  # noqa: PLW0603
    model_result = load_transcription_model(config)
    if model_result["ok"] is False:
        return
    model = model_result["value"]
    # MLX streams are thread-bound. Materialize every weight and flush the
    # device queue on THIS thread before publishing, or the main thread's
    # generate() dies with "There is no Stream(cpu, 1) in current thread".
    _mx.eval(model.parameters())
    warm_up_model(model)
    _mx.synchronize()
    _preloaded_model = model


def take_preloaded_model() -> _ParakeetModelLike | None:
    """Return and clear the preloaded model, if the background load finished."""
    global _preloaded_model  # noqa: PLW0603
    model = _preloaded_model
    _preloaded_model = None
    return model


def transcribe_audio(artifact_path: AudioArtifactPath, config: KoeConfig, /) -> TranscriptionResult:
    """Transcribe one WAV artifact, reusing the preloaded model when available."""
    model = take_preloaded_model()
    if model is None:
        model_result = load_transcription_model(config)
        if model_result["ok"] is False:
            return {"kind": "error", "error": model_result["error"]}
        model = model_result["value"]
    return transcribe_audio_with_model(model, artifact_path)


def load_transcription_model(
    config: KoeConfig, /
) -> Result[_ParakeetModelLike, TranscriptionError]:
    """Construct the Parakeet model on the Metal device, shaping load failures."""
    try:
        model = _parakeet.from_pretrained(config["parakeet_model"])
    except Exception as error:
        return {
            "ok": False,
            "error": _transcription_error(f"model load failed: {error}"),
        }
    return {"ok": True, "value": cast("_ParakeetModelLike", model)}


def warm_up_model(model: _ParakeetModelLike, /) -> None:
    """Compile Metal kernels with one throwaway generate on a second of silence.

    Intended for a background thread while recording is still in progress: the
    first generate in a process pays roughly a second of kernel compilation;
    every generate after runs at ~60-80x realtime. Failures are swallowed —
    warm-up is an optimization, and the real transcription surfaces any genuine
    fault as a typed error moments later.
    """
    try:
        silence = np.zeros(model.preprocessor_config.sample_rate, dtype=np.float32)
        mel = _parakeet_audio.get_logmel(_mx.array(silence), model.preprocessor_config)
        model.generate(mel)
    except Exception:
        return


def transcribe_audio_with_model(
    model: _ParakeetModelLike, artifact_path: AudioArtifactPath, /
) -> TranscriptionResult:
    """Transcribe a koe-authored WAV with an already-loaded Parakeet model."""
    try:
        samples, sample_rate = cast(
            "tuple[_SamplesLike, int]",
            soundfile.read(str(artifact_path), dtype="float32"),
        )
    except Exception as error:
        return {"kind": "error", "error": _transcription_error(f"wav read failed: {error}")}

    expected_rate = model.preprocessor_config.sample_rate
    if sample_rate != expected_rate:
        return {
            "kind": "error",
            "error": _transcription_error(
                f"sample rate mismatch: artifact is {sample_rate} Hz,"
                f" model expects {expected_rate} Hz"
            ),
        }

    if samples.ndim != 1:
        # Koe records mono; a multi-channel artifact means an upstream capture
        # bug. Refuse loudly rather than downmix into silently wrong text.
        return {
            "kind": "error",
            "error": _transcription_error(
                f"expected mono artifact, got {samples.ndim}-dimensional samples"
            ),
        }

    try:
        mel = _parakeet_audio.get_logmel(_mx.array(samples), model.preprocessor_config)
        results = model.generate(mel)
    except Exception as error:
        return {"kind": "error", "error": _transcription_error(f"inference failed: {error}")}

    transcript_text = results[0].text.strip() if results else ""
    if transcript_text == "":
        return {"kind": "empty"}
    return {"kind": "text", "text": transcript_text}


def _transcription_error(message: str) -> TranscriptionError:
    """Create a typed transcription error payload.

    ``cuda_available`` is a CUDA-engine diagnostic carried by the shared error
    type; there is no CUDA on darwin, so it is always False here.
    """
    return {
        "category": "transcription",
        "message": message,
        "cuda_available": False,
    }
