"""Koe M1 runtime configuration constants."""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, TypedDict


class KoeConfig(TypedDict, total=True):
    hotkey_combo: str
    sample_rate: int
    audio_channels: int
    audio_format: Literal["float32"]
    whisper_model: str
    whisper_device: Literal["cuda"]
    whisper_compute_type: str
    paste_key_modifier: str
    paste_key: str
    lock_file_path: Path
    temp_dir: Path
    usage_log_path: Path


DEFAULT_CONFIG: Final[KoeConfig] = {
    "hotkey_combo": "<super>+<shift>+v",
    "sample_rate": 16_000,
    "audio_channels": 1,
    "audio_format": "float32",
    "whisper_model": "base.en",
    "whisper_device": "cuda",
    "whisper_compute_type": "float16",
    "paste_key_modifier": "ctrl",
    "paste_key": "v",
    "lock_file_path": Path("/tmp/koe.lock"),
    "temp_dir": Path("/tmp"),
    "usage_log_path": Path("/tmp/koe-usage.jsonl"),
}
