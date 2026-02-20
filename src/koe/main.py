"""Koe M1 CLI entrypoint contracts."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, assert_never

from koe.config import DEFAULT_CONFIG, KoeConfig

if TYPE_CHECKING:
    from koe.types import ExitCode, PipelineOutcome


def main() -> None:
    try:
        outcome = run_pipeline(DEFAULT_CONFIG)
        sys.exit(outcome_to_exit_code(outcome))
    except Exception:
        sys.exit(2)


def run_pipeline(config: KoeConfig, /) -> PipelineOutcome:
    _ = config
    raise NotImplementedError("Implemented in Sections 2-6")


def outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode:
    match outcome:
        case "success":
            return 0
        case (
            "no_focus"
            | "no_speech"
            | "error_dependency"
            | "error_audio"
            | "error_transcription"
            | "error_insertion"
            | "already_running"
        ):
            return 1
        case "error_unexpected":
            return 2
        case _ as unreachable:
            assert_never(unreachable)
