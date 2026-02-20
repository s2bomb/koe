from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest

from koe import notify

if TYPE_CHECKING:
    from koe.types import KoeError, NotificationKind


@pytest.mark.parametrize(
    ("kind", "error"),
    [
        (
            cast("NotificationKind", "error_dependency"),
            cast(
                "KoeError",
                {"category": "dependency", "message": "missing xdotool", "missing_tool": "xdotool"},
            ),
        ),
        (
            cast("NotificationKind", "error_focus"),
            cast("KoeError", {"category": "focus", "message": "no focused window"}),
        ),
        (
            cast("NotificationKind", "already_running"),
            cast(
                "KoeError",
                {
                    "category": "already_running",
                    "message": "another koe instance is active",
                    "lock_file": "/tmp/koe.lock",
                    "conflicting_pid": 41,
                },
            ),
        ),
    ],
)
def test_send_notification_swallows_backend_failures(
    kind: NotificationKind, error: KoeError
) -> None:
    with patch("subprocess.run", side_effect=RuntimeError("backend down")):
        notify.send_notification(kind, error)
