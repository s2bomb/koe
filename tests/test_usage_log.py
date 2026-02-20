from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest
from typeguard import check_type

from koe.config import DEFAULT_CONFIG
from koe.types import UsageLogRecord
from koe.usage_log import write_usage_log_record

if TYPE_CHECKING:
    from pathlib import Path

    from koe.config import KoeConfig
    from koe.types import PipelineOutcome

EXPECTED_FIRST_DURATION_MS = 123
EXPECTED_RECORD_COUNT = 3
UUID4_VERSION = 4


def _config_with_usage_log(usage_log_path: Path) -> KoeConfig:
    return cast("KoeConfig", {**DEFAULT_CONFIG, "usage_log_path": usage_log_path})


def _read_jsonl(path: Path) -> list[UsageLogRecord]:
    records: list[UsageLogRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = json.loads(line)
        check_type(parsed, UsageLogRecord)
        records.append(parsed)
    return records


def test_write_usage_log_record_appends_one_jsonl_record_with_required_shape(
    tmp_path: Path,
) -> None:
    usage_log_path = tmp_path / "koe-usage.jsonl"
    config = _config_with_usage_log(usage_log_path)

    write_usage_log_record(
        config,
        "success",
        invoked_at="2026-02-20T09:00:00+00:00",
        duration_ms=123,
    )

    records = _read_jsonl(usage_log_path)
    assert len(records) == 1
    assert records[0]["outcome"] == "success"
    assert records[0]["invoked_at"] == "2026-02-20T09:00:00+00:00"
    assert records[0]["duration_ms"] == EXPECTED_FIRST_DURATION_MS


def test_write_usage_log_record_multiple_calls_append_and_generate_distinct_uuid4_run_ids(
    tmp_path: Path,
) -> None:
    usage_log_path = tmp_path / "koe-usage.jsonl"
    config = _config_with_usage_log(usage_log_path)

    write_usage_log_record(
        config, "success", invoked_at="2026-02-20T09:00:00+00:00", duration_ms=10
    )
    write_usage_log_record(
        config,
        "already_running",
        invoked_at="2026-02-20T09:00:01+00:00",
        duration_ms=11,
    )
    write_usage_log_record(
        config, "error_dependency", invoked_at="2026-02-20T09:00:02+00:00", duration_ms=12
    )

    records = _read_jsonl(usage_log_path)
    assert len(records) == EXPECTED_RECORD_COUNT

    run_ids = [record["run_id"] for record in records]
    assert len(set(run_ids)) == EXPECTED_RECORD_COUNT

    for run_id in run_ids:
        parsed = uuid.UUID(run_id)
        assert parsed.version == UUID4_VERSION
        assert str(parsed) == run_id


@pytest.mark.parametrize(
    "outcome",
    [
        "success",
        "already_running",
        "no_focus",
        "no_speech",
        "error_dependency",
        "error_audio",
        "error_transcription",
        "error_insertion",
        "error_unexpected",
    ],
)
def test_write_usage_log_record_outcome_passthrough_is_total(
    tmp_path: Path,
    outcome: PipelineOutcome,
) -> None:
    usage_log_path = tmp_path / "koe-usage.jsonl"
    config = _config_with_usage_log(usage_log_path)

    write_usage_log_record(config, outcome, invoked_at="2026-02-20T09:00:00+00:00", duration_ms=1)

    records = _read_jsonl(usage_log_path)
    assert len(records) == 1
    assert records[0]["outcome"] == outcome


@pytest.mark.parametrize(
    "patch_target",
    ["koe.usage_log.os.open", "koe.usage_log.json.dumps"],
)
def test_write_usage_log_record_is_non_raising_on_write_failure_emits_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    patch_target: str,
) -> None:
    usage_log_path = tmp_path / "koe-usage.jsonl"
    config = _config_with_usage_log(usage_log_path)

    with patch(patch_target, side_effect=OSError("boom"), create=True):
        write_usage_log_record(
            config, "success", invoked_at="2026-02-20T09:00:00+00:00", duration_ms=1
        )

    captured = capsys.readouterr()
    assert "usage log" in captured.err.lower()
