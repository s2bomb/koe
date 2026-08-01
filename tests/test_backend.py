from __future__ import annotations

from koe.backend import determine_backend


def test_env_override_wins_over_platform() -> None:
    assert determine_backend("darwin", {"KOE_BACKEND": "x11"}) == "x11"
    assert determine_backend("linux", {"KOE_BACKEND": "darwin"}) == "darwin"
    assert determine_backend("linux", {"KOE_BACKEND": "wayland", "DISPLAY": ":1"}) == "wayland"


def test_darwin_platform_detected_without_override() -> None:
    assert determine_backend("darwin", {}) == "darwin"


def test_wayland_detected_from_session_type_without_display() -> None:
    assert determine_backend("linux", {"XDG_SESSION_TYPE": "wayland"}) == "wayland"


def test_wayland_session_with_display_falls_back_to_x11() -> None:
    env = {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":1"}
    assert determine_backend("linux", env) == "x11"


def test_plain_linux_defaults_to_x11() -> None:
    assert determine_backend("linux", {}) == "x11"


def test_unknown_override_value_is_ignored() -> None:
    assert determine_backend("darwin", {"KOE_BACKEND": "beos"}) == "darwin"
