from __future__ import annotations

from unittest.mock import patch

import pytest

from koe import window


@pytest.fixture(autouse=True)
def _pin_darwin_backend(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("KOE_BACKEND", "darwin")


def test_context_check_passes_without_any_window_system() -> None:
    result = window.check_x11_context()

    assert result == {"ok": True, "value": None}


def test_focus_gate_is_vacuous_and_queries_nothing() -> None:
    """D6: clipboard is the guarantee — darwin proceeds regardless of focus."""
    with patch("subprocess.run") as run_mock:
        result = window.check_focused_window()

    assert result["ok"] is True
    assert result["value"]["title"] == ""
    run_mock.assert_not_called()
