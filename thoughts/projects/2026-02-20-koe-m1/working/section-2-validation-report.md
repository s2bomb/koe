# Validation Report: Koe M1 Section 2 Invocation, Focus Gate, and Concurrency Guard

Plan: `thoughts/plans/2026-02-20-koe-m1-section-2-invocation-focus-guard-plan.md`
Date: 2026-02-20
Validator: `validate-plan` orchestration with `validate-plan-clone` phase audits

## Overall Verdict

- Section 2 is now validated green for functional and gate criteria.
- Previous blockers were remediated: full lint/typecheck/test bundle is green and Phase 1/3 test commits now exist in git history.

## Implementation Status by Phase

- Phase 1 (Type-Surface Tests and Fixtures): **Implemented**.
  - Evidence: `tests/section2_static_fixtures.py:15`, `tests/test_types.py:191`, `tests/test_main.py:101`.
- Phase 2 (Atomic Type Extension + Exit Mapping): **Implemented**.
  - Evidence: `src/koe/types.py:13`, `src/koe/types.py:102`, `src/koe/main.py:81`, `tests/section1_static_fixtures.py:62`.
- Phase 3 (Runtime Contract Tests, Red): **Implemented**.
  - Evidence: `tests/test_hotkey.py:13`, `tests/test_window.py:21`, `tests/test_notify.py:42`, `tests/test_main.py:115`.
- Phase 4 (Concurrency Guard API): **Implemented**.
  - Evidence: `src/koe/hotkey.py:39`, `src/koe/hotkey.py:59`.
- Phase 5 (X11/Notification/Preflight Boundaries): **Implemented**.
  - Evidence: `src/koe/window.py:12`, `src/koe/notify.py:12`, `src/koe/main.py:26`.
- Phase 6 (Run Pipeline Orchestration): **Implemented**.
  - Evidence: `src/koe/main.py:53`, `tests/test_main.py:197`.

## Automated Verification Results

Executed in this re-validation run:

```bash
make lint && make typecheck && make test
```

- `make lint`: **PASS**.
- `make typecheck`: **PASS** (`0 errors, 0 warnings`).
- `make test`: **PASS** (`67 passed`).

## Requirements Coverage (Section 2 ACs)

Source requirements: `thoughts/projects/2026-02-20-koe-m1/spec.md:45` through `thoughts/projects/2026-02-20-koe-m1/spec.md:50`.

- AC1 (external trigger, no daemon): one-shot CLI path with no daemonized loop in `src/koe/main.py:18`; ordering proven by `tests/test_main.py:197`.
- AC2 (focus check before recording): `run_pipeline` stage order validates X11 + focus before Section 3 handoff in `src/koe/main.py:66` and `src/koe/main.py:71`; verified by `tests/test_main.py:197`.
- AC3 (no focus -> notify + exit): `src/koe/main.py:73` emits `"error_focus"` and returns `"no_focus"`; covered by `tests/test_main.py:169`.
- AC4 (single-instance guard blocks concurrent run): lock acquisition in `src/koe/hotkey.py:39` returns typed contention error on second invocation; covered by `tests/test_hotkey.py:21`.
- AC5 (explicit already-running feedback): `src/koe/main.py:61` emits `"already_running"`; typed payload in `src/koe/types.py:102`; covered by `tests/test_main.py:141` and `tests/test_types.py:191`.
- AC6 (startup dependency failures explicit + safe exit): `src/koe/main.py:26` plus `src/koe/window.py:12` return typed dependency errors and short-circuit safely; covered by `tests/test_main.py:28` and `tests/test_main.py:115`.

## Remediation Verification

- Previous typecheck failures are resolved (`tests/section2_static_fixtures.py`, `tests/test_main.py`, `tests/test_notify.py` now typecheck clean).
- Missing planned test-phase commits are now present:
  - `7c4b55c` (`test: add section 2 type-surface proofs`)
  - `c2bfa84` (`test: add section 2 runtime contract tests`)

## Non-Blocking Findings

- `src/koe/window.py:40` performs an internal `check_x11_context()` call even though `run_pipeline` already checks X11 context at `src/koe/main.py:66`; this is redundant but does not break Section 2 acceptance criteria.
- `src/koe/hotkey.py:66` and `src/koe/notify.py:22` swallow cleanup/notification transport failures without logging; behavior matches non-raising contract but limits observability.
- Git history indicates tests were committed after implementation commits; current code and gates validate green, but red-first sequencing evidence remains weak.

## Final Validation Decision

- **Validation status: PASS.**
- Section 2 acceptance criteria (AC1-AC6), test obligations (T-01..T-21), and final gate commands are satisfied after remediation.
