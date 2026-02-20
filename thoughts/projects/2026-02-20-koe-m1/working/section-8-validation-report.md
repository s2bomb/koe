# Section 8 Validation Report

Date: 2026-02-20
Section: Section 8 - Omarchy Hotkey Trigger and Per-Run Usage Logging Validation (Wayland)
Plan: `thoughts/plans/2026-02-20-koe-m1-section-8-omarchy-usage-logging-plan.md`

## Automated Validation

- `uv run pytest tests/test_hotkey.py tests/test_usage_log.py tests/test_main.py tests/section8_static_fixtures.py` -> pass
- `make lint && make typecheck && make test` -> pass

## Manual Check M-01 (Static binding contract)

Status: pass

Evidence:

1. Active Hyprland source chain includes:
   - `~/.local/share/omarchy/default/hypr/bindings/media.conf`
   - `~/.local/share/omarchy/default/hypr/bindings/clipboard.conf`
   - `~/.local/share/omarchy/default/hypr/bindings/tiling-v2.conf`
   - `~/.local/share/omarchy/default/hypr/bindings/utilities.conf`
   - `~/.config/hypr/bindings.conf`
2. User binding added:
   - `bind = SUPER SHIFT, V, exec, koe` in `~/.config/hypr/bindings.conf`
3. Duplicate check:
   - Exactly one `exec, koe` binding found across active user config.
   - A `SUPER SHIFT, V` entry exists in `~/.local/share/omarchy/default/hypr/bindings/tiling.conf`, but that file is not sourced by `~/.config/hypr/hyprland.conf` (which sources `tiling-v2.conf`), so it is inactive.

## Manual Check M-02 (Runtime hotkey activation)

Status: pending human verification

Required steps:

1. Record baseline line count of `/tmp/koe-usage.jsonl`.
2. Press `SUPER+SHIFT+V` once in an active Omarchy session.
3. Confirm line count increments by exactly 1.
4. Confirm latest JSON record parses and outcome matches observed run result.
5. Trigger contention case and confirm an additional record with `outcome` set to `already_running`.

Notes:

- This check requires live compositor interaction and cannot be fully automated from the CLI environment.
