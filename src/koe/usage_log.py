"""Per-invocation usage and transcription log writing for Koe."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from pathlib import Path

    from koe.config import KoeConfig
    from koe.types import PipelineOutcome, UsageLogRecord


def ensure_data_dir(config: KoeConfig, /) -> None:
    """Create the persistent data directory if it does not exist."""
    try:
        config["data_dir"].mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"data dir creation failed: {error}", file=sys.stderr)


def write_usage_log_record(
    config: KoeConfig,
    outcome: PipelineOutcome,
    /,
    *,
    invoked_at: str,
    duration_ms: int,
) -> None:
    """Append one JSONL usage record and never raise."""
    try:
        record: UsageLogRecord = {
            "run_id": str(uuid4()),
            "invoked_at": invoked_at,
            "outcome": outcome,
            "duration_ms": duration_ms,
        }
        _append_jsonl(config["usage_log_path"], record)
    except Exception as error:
        print(f"usage log write failed: {error}", file=sys.stderr)


def write_transcription_record(config: KoeConfig, text: str, /) -> None:
    """Append one JSONL transcription record and never raise.

    Every successful transcription is saved for later analysis. Records
    include timestamp, text, and word count.
    """
    try:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "text": text,
            "word_count": len(text.split()),
        }
        _append_jsonl(config["transcription_log_path"], record)
    except Exception as error:
        print(f"transcription log write failed: {error}", file=sys.stderr)


def _append_jsonl(path: Path, record: object, /) -> None:
    """Append a JSON record to a JSONL file with restrictive permissions."""
    payload = json.dumps(record)
    file_descriptor = os.open(
        path,
        os.O_APPEND | os.O_CREAT | os.O_WRONLY,
        0o600,
    )
    with os.fdopen(file_descriptor, "a", encoding="utf-8") as handle:
        handle.write(f"{payload}\n")
