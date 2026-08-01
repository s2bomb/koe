"""Koe M1 runtime configuration constants."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final, Literal, TypedDict

# XDG Base Directory: ~/.local/share/koe/ for persistent user data.
_XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
_DATA_DIR = _XDG_DATA_HOME / "koe"


class KoeConfig(TypedDict, total=True):
    hotkey_combo: str
    sample_rate: int
    audio_channels: int
    audio_format: Literal["float32"]
    whisper_model: str
    parakeet_model: str
    strip_filler_words: bool
    whisper_device: Literal["cuda"]
    whisper_compute_type: str
    whisper_cpu_fallback: bool
    whisper_cpu_compute_type: str
    paste_key_modifier: str
    paste_key: str
    lock_file_path: Path
    temp_dir: Path
    data_dir: Path
    usage_log_path: Path
    transcription_log_path: Path


DEFAULT_CONFIG: Final[KoeConfig] = {
    "hotkey_combo": "<super>+<shift>+v",
    "sample_rate": 16_000,
    "audio_channels": 1,
    "audio_format": "float32",
    "whisper_model": "base.en",
    # Darwin engine (transcribe_darwin.py): HuggingFace repo id, cached under
    # ~/.cache/huggingface after the first download. Unused on Linux.
    "parakeet_model": "mlx-community/parakeet-tdt-0.6b-v3",
    # Strip um/uh disfluencies from the DELIVERED text (clipboard/paste).
    # The transcription log always archives the verbatim transcript.
    "strip_filler_words": True,
    "whisper_device": "cuda",
    "whisper_compute_type": "float16",
    # When the GPU attempt fails because CUDA is unavailable or out of VRAM
    # (e.g. a game holds the memory), retry on CPU so transcription still works.
    "whisper_cpu_fallback": True,
    "whisper_cpu_compute_type": "int8",
    "paste_key_modifier": "ctrl",
    "paste_key": "v",
    "lock_file_path": Path("/tmp/koe.lock"),
    "temp_dir": Path("/tmp"),
    "data_dir": _DATA_DIR,
    "usage_log_path": _DATA_DIR / "usage.jsonl",
    "transcription_log_path": _DATA_DIR / "transcriptions.jsonl",
}
