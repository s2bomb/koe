from __future__ import annotations

from typing import TYPE_CHECKING

from koe.main import outcome_to_exit_code
from koe.notify import send_notification

if TYPE_CHECKING:
    from collections.abc import Callable

    from koe.types import ExitCode, NotificationKind, PipelineOutcome


def t6sf_01_send_notification_signature_contract() -> None:
    send_sig: Callable[[NotificationKind], None] = send_notification
    _ = send_sig


def t6sf_02_outcome_to_exit_code_signature_contract() -> None:
    exit_sig: Callable[[PipelineOutcome], ExitCode] = outcome_to_exit_code
    _ = exit_sig
