from __future__ import annotations

from pathlib import Path

import pytest
from typeguard import TypeCheckError, check_type

from koe.config import DEFAULT_CONFIG, KoeConfig

EXPECTED_SAMPLE_RATE = 16_000


def test_koe_config_requires_all_fields() -> None:
    check_type(DEFAULT_CONFIG, KoeConfig)


def test_koe_config_rejects_missing_required_field() -> None:
    incomplete = {
        "hotkey_combo": "<super>+<shift>+v",
        "sample_rate": 16_000,
        "audio_channels": 1,
        "audio_format": "float32",
        "whisper_model": "base.en",
        "whisper_device": "cuda",
        "whisper_compute_type": "float16",
        "paste_key_modifier": "ctrl",
        "lock_file_path": Path("/tmp/koe.lock"),
        "temp_dir": Path("/tmp"),
    }

    with pytest.raises(TypeCheckError):
        check_type(incomplete, KoeConfig)


def test_default_config_matches_section_1_defaults() -> None:
    check_type(DEFAULT_CONFIG, KoeConfig)
    assert DEFAULT_CONFIG["sample_rate"] == EXPECTED_SAMPLE_RATE
    assert DEFAULT_CONFIG["audio_channels"] == 1
    assert DEFAULT_CONFIG["audio_format"] == "float32"
    assert DEFAULT_CONFIG["whisper_device"] == "cuda"


def test_default_config_is_override_spreadable() -> None:
    override: KoeConfig = {**DEFAULT_CONFIG, "whisper_model": "tiny.en"}
    check_type(override, KoeConfig)
    assert override["whisper_model"] == "tiny.en"
