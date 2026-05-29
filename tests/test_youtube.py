from __future__ import annotations

import wave
from typing import TYPE_CHECKING

from koe.youtube import (
    bundle_dir_name,
    chunk_wav_audio,
    format_transcript_lines,
    merge_chunk_transcripts,
    resolve_bundle_dir,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_test_wav(path: Path, /, *, seconds: int, sample_rate: int = 4) -> None:
    frame_count = seconds * sample_rate
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes((b"\x01\x00") * frame_count)


def test_chunk_wav_audio_writes_overlapping_chunks(tmp_path: Path) -> None:
    source_path = tmp_path / "full.wav"
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    _write_test_wav(source_path, seconds=8)

    result = chunk_wav_audio(source_path, chunks_dir, chunk_seconds=3, overlap_seconds=1.0)

    assert result["ok"] is True
    chunk_paths = result["value"]
    assert [path.name for path in chunk_paths] == [
        "chunk-0001.wav",
        "chunk-0002.wav",
        "chunk-0003.wav",
        "chunk-0004.wav",
    ]

    frame_counts: list[int] = []
    for chunk_path in chunk_paths:
        with wave.open(str(chunk_path), "rb") as handle:
            frame_counts.append(handle.getnframes())

    assert frame_counts == [12, 12, 12, 8]


def test_merge_chunk_transcripts_trims_simple_overlap_words() -> None:
    merged = merge_chunk_transcripts(
        [
            "We should keep the local files together for review.",
            "for review. Then we can compare the transcript output.",
        ],
        max_overlap_words=6,
    )

    assert (
        merged == "We should keep the local files together for review. "
        "Then we can compare the transcript output."
    )


def test_format_transcript_lines_splits_sentences_into_lines() -> None:
    transcript = "First sentence. Second sentence? Third sentence!"

    assert (
        format_transcript_lines(transcript) == "First sentence.\nSecond sentence?\nThird sentence!"
    )


def test_format_transcript_lines_wraps_long_sentence_without_punctuation() -> None:
    transcript = "one two three four five six seven"

    assert (
        format_transcript_lines(transcript, max_words_per_line=3)
        == "one two three\nfour five six\nseven"
    )


def test_bundle_dir_name_uses_title_slug_plus_video_id() -> None:
    bundle_name = bundle_dir_name(
        "Handmade Hero Day 051 - Separating Entities By Update Frequency",
        "RQUP4ql86k0",
    )

    assert (
        bundle_name == "handmade-hero-day-051-separating-entities-by-update-frequency-RQUP4ql86k0"
    )


def test_resolve_bundle_dir_migrates_legacy_video_id_directory(tmp_path: Path) -> None:
    legacy_dir = tmp_path / "RQUP4ql86k0"
    legacy_dir.mkdir()
    marker_path = legacy_dir / "metadata.json"
    marker_path.write_text("{}", encoding="utf-8")

    resolved_dir = resolve_bundle_dir(
        tmp_path,
        "Handmade Hero Day 051 - Separating Entities By Update Frequency",
        "RQUP4ql86k0",
    )

    assert (
        resolved_dir
        == tmp_path / "handmade-hero-day-051-separating-entities-by-update-frequency-RQUP4ql86k0"
    )
    assert resolved_dir.exists()
    assert not legacy_dir.exists()
    assert (resolved_dir / "metadata.json").read_text(encoding="utf-8") == "{}"
