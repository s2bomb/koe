from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from koe.main import main, outcome_to_exit_code

if TYPE_CHECKING:
    from koe.types import ExitCode, PipelineOutcome


def test_main_maps_unexpected_exception_to_exit_2() -> None:
    with (
        patch("koe.main.run_pipeline", side_effect=Exception("boom")),
        patch("sys.exit") as exit_mock,
    ):
        main()

    exit_mock.assert_called_once_with(2)


@pytest.mark.xfail(
    reason="Deferred until Sections 2-6 provide stage functions and cleanup hooks",
    strict=True,
)
def test_run_pipeline_preserves_cleanup_on_mid_pipeline_failure() -> None:
    raise AssertionError("Deferred runtime contract proof for T-21")


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("success", 0),
        ("no_focus", 1),
        ("no_speech", 1),
        ("error_dependency", 1),
        ("error_audio", 1),
        ("error_transcription", 1),
        ("error_insertion", 1),
        ("error_unexpected", 2),
    ],
)
def test_outcome_to_exit_code_is_total(outcome: PipelineOutcome, expected: ExitCode) -> None:
    assert outcome_to_exit_code(outcome) == expected
