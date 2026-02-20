from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from koe.usage_log import write_usage_log_record

if TYPE_CHECKING:
    from koe.config import KoeConfig
    from koe.types import PipelineOutcome, UsageLogRecord


class _UsageLogWriter(Protocol):
    def __call__(
        self,
        config: KoeConfig,
        outcome: PipelineOutcome,
        /,
        *,
        invoked_at: str,
        duration_ms: int,
    ) -> None: ...


def t8sf_write_usage_log_record_signature_contract() -> None:
    writer: _UsageLogWriter = write_usage_log_record
    _ = writer


def t8sf_koe_config_includes_usage_log_path(config: KoeConfig) -> None:
    usage_log_path = config["usage_log_path"]
    _ = usage_log_path


def t8sf_usage_log_record_contract(record: UsageLogRecord) -> None:
    _ = record["run_id"]
    _ = record["invoked_at"]
    _ = record["outcome"]
    _ = record["duration_ms"]
