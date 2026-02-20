"""Per-invocation usage log writing for Koe."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from koe.config import KoeConfig
    from koe.types import PipelineOutcome, UsageLogRecord


def write_usage_log_record(
    config: KoeConfig,
    outcome: PipelineOutcome,
    /,
    *,
    invoked_at: str,
    duration_ms: int,
) -> None:
    """Append one JSONL usage record and never raise."""
    record: UsageLogRecord = {
        "run_id": str(uuid4()),
        "invoked_at": invoked_at,
        "outcome": outcome,
        "duration_ms": duration_ms,
    }

    try:
        payload = json.dumps(record)
        with config["usage_log_path"].open("a", encoding="utf-8") as handle:
            handle.write(f"{payload}\n")
    except Exception as error:
        print(f"usage log write failed: {error}", file=sys.stderr)
