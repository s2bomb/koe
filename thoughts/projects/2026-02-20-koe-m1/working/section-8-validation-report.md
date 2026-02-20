# Section 8 Validation Report

Date: 2026-02-20
Section: Section 8 - Omarchy Hotkey Trigger and Per-Run Usage Logging Validation (Wayland)
Plan: `thoughts/plans/2026-02-20-koe-m1-section-8-omarchy-usage-logging-plan.md`

## Final Verdict

Verdict: **PASS WITH ISSUES**

Section 8 behavior is implemented and validated by automated checks, but one blocker remains before durable sign-off.

## Automated Validation

- `uv run pytest tests/test_usage_log.py tests/test_main.py tests/section8_static_fixtures.py tests/test_hotkey.py -v` -> pass (63 passed)
- `make lint && make typecheck && make test` -> pass (ruff clean, pyright clean, full test suite green)

## Requirement Validation (AC1-AC5)

1. AC1 (Omarchy hotkey triggers `koe`): **met**
   - Verified `bind = SUPER SHIFT, V, exec, koe` in `~/.config/hypr/bindings.conf`.
2. AC2 (one activation -> one run record): **met**
   - `src/koe/main.py` logs once per `main()` invocation before `sys.exit`.
3. AC3 (blocked attempts produce distinct `already_running` record): **met**
   - Covered by outcome passthrough and tests for contention outcomes.
4. AC4 (dependency/config failure logs failed-attempt safely): **met**
   - Non-success outcomes log through the same boundary and map to safe exit codes.
5. AC5 (automated + manual validation path): **partial**
   - Automated checks are complete and passing.
   - Runtime manual M-02 remains pending human compositor verification.

## Blockers

1. **Section 8 test artifacts are not durably committed in git**
   - `tests/test_usage_log.py` and `tests/section8_static_fixtures.py` are untracked.
   - Section 8 deltas in `tests/test_main.py` and `tests/test_hotkey.py` are unstaged/uncommitted.
   - Impact: Section 8 validation can pass in the current working tree but is not reproducible from committed history.

## Non-Blockers

1. **M-02 runtime hotkey check is pending human execution**
   - Expected by plan flow; requires live Omarchy session.
2. **Minor hardening opportunity in `src/koe/usage_log.py`**
   - `uuid4()` record construction happens before the `try` block; low-risk but could be moved inside for maximal non-raising guarantees.

## Manual Checks

### M-01 (Static binding contract)

Status: pass

Evidence:

1. Active Hyprland source chain includes:
   - `~/.local/share/omarchy/default/hypr/bindings/media.conf`
   - `~/.local/share/omarchy/default/hypr/bindings/clipboard.conf`
   - `~/.local/share/omarchy/default/hypr/bindings/tiling-v2.conf`
   - `~/.local/share/omarchy/default/hypr/bindings/utilities.conf`
   - `~/.config/hypr/bindings.conf`
2. User binding present:
   - `bind = SUPER SHIFT, V, exec, koe` in `~/.config/hypr/bindings.conf`
3. Duplicate/conflict check:
   - Exactly one active `exec, koe` binding.
   - A `SUPER SHIFT, V` entry exists in `~/.local/share/omarchy/default/hypr/bindings/tiling.conf`, but that file is not sourced (active chain uses `tiling-v2.conf`).

### M-02 (Runtime hotkey activation)

Status: pending human verification

Required steps:

1. Record baseline line count of `/tmp/koe-usage.jsonl`.
2. Press `SUPER+SHIFT+V` once in an active Omarchy session.
3. Confirm line count increments by exactly 1.
4. Confirm latest JSON record parses and outcome matches observed run result.
5. Trigger contention case and confirm an additional record with `outcome` set to `already_running`.
