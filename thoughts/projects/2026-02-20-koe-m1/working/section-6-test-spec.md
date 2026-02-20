---
title: "Section 6 User Feedback and Exit Semantics Test Specification"
date: 2026-02-20
status: approved
design_source: "thoughts/design/2026-02-20-section-6-notify-exit-semantics.md"
spec_source: "thoughts/projects/2026-02-20-koe-m1/spec.md"
research_source: "thoughts/projects/2026-02-20-koe-m1/working/section-6-research.md"
project_section: "Section 6: User Feedback and Error Surfaces"
---

# Test Specification: Section 6 User Feedback and Exit Semantics

## Purpose

This document defines proof obligations for Section 6 API contracts. Each test maps to a contract in the approved design and proves behavior that Pyright cannot prove: runtime payload values, dispatch timing/order, non-raising notification transport, and exit semantics under exceptions.

## Test Infrastructure

**Framework**: `pytest` (`pyproject.toml:24`)
**Test location**: `tests/`
**Patterns to follow**:
- Mocking/stage isolation in pipeline tests: `tests/test_main.py:116`
- Ordering via `events` list + `side_effect`: `tests/test_main.py:538`
- Total mapping via parametrization: `tests/test_main.py:98`
- Notification subprocess patching: `tests/test_notify.py:14`
- Static type fixtures via `assert_type`/`assert_never`: `tests/section1_static_fixtures.py:51`
**Utilities available**:
- `typeguard.check_type` for runtime shape checks: `tests/test_types.py:30`
- `tmp_path` for lock/artifact paths: `tests/test_main.py:311`
**Run command**: `make test` (or targeted: `uv run pytest tests/test_notify.py tests/test_main.py`)

## API Surface

| Contract | Signature | Design Reference | Tests |
|----------|-----------|------------------|-------|
| Notification transport API | `send_notification(kind: NotificationKind, error: KoeError | None = None) -> None` | `2026-02-20-section-6-notify-exit-semantics.md:90` | T6N-01, T6N-02, T6N-03, T6N-04, T6N-05 |
| Notification payload mapping | `_notification_payload(kind: NotificationKind, error: KoeError | None) -> tuple[str, str]` | `2026-02-20-section-6-notify-exit-semantics.md:102` | T6N-01, T6N-02, T6N-03, T6N-04 |
| Error message extraction helper | `_error_message(error: KoeError | None, fallback: str) -> str` | `2026-02-20-section-6-notify-exit-semantics.md:116` | T6N-02, T6N-04 |
| Exit mapping totality | `outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode` | `2026-02-20-section-6-notify-exit-semantics.md:128` | T6M-01 |
| CLI exception exit behavior | `main() -> None` | `2026-02-20-section-6-notify-exit-semantics.md:138` | T6M-02 |
| Pipeline notification dispatch semantics | `run_pipeline(config: KoeConfig, /) -> PipelineOutcome` | `2026-02-20-section-6-notify-exit-semantics.md:148` | T6M-03a..T6M-03i, T6M-04a, T6M-04b, T6M-05 |
| Static API surface stability | compile-time callable contracts | `2026-02-20-section-6-notify-exit-semantics.md:457` | T6SF-01, T6SF-02 |

## Proof Obligations

### `send_notification` + `_notification_payload` + `_error_message`

Design references: `...notify-exit-semantics.md:90`, `:102`, `:116`, `:160`
Depends on: `NotificationKind` and `KoeError` closed unions in `src/koe/types.py`

#### T6N-01: Lifecycle payload matrix is exact for all 4 lifecycle kinds

**Contract**: Lifecycle kinds map to exact static `(title, message)` pairs.
**Setup**: Parametrize `recording_started`, `processing`, `completed`, `no_speech`; patch `subprocess.run`; call `send_notification(kind)`.
**Expected**: Called with `['notify-send', 'Koe', expected_message]` where messages are exactly `Recording…`, `Processing…`, `Transcription complete`, `No speech detected`.
**Discriminating power**: Fails dynamic/derived message implementations (for example `kind.replace('_', ' ')`).
**Invariant**: I2, I4.
**Allowed variation**: Internal branch shape (`if` vs `match`) may change; payloads must not.
**Assertion scope rationale**: Exact subprocess argument list is the smallest observable proof of payload correctness.
**Fragility check**: Does not assert call count beyond one invocation in the test case; avoids coupling to unrelated transport internals.

---

#### T6N-02: Error kinds always surface `error["message"]` for all 6 error kinds

**Contract**: Error payload message uses provided typed error text when error is non-`None`.
**Setup**: Parametrize all six error kinds with matching `KoeError` instances containing distinct messages; patch `subprocess.run`; call `send_notification(kind, error)`.
**Expected**: Third subprocess arg equals the exact `error['message']` string.
**Discriminating power**: Fails implementations that drop runtime error context or substitute fallback text.
**Invariant**: I3.
**Allowed variation**: Error dict may include additional fields; only message extraction is contractually fixed.
**Assertion scope rationale**: Message argument alone is sufficient to prove extraction behavior.
**Fragility check**: Avoid full-object equality on error dicts.

---

#### T6N-03: Error title matrix is exact and subsystem-specific for all 6 error kinds

**Contract**: Error kinds use non-generic subsystem-specific titles.
**Setup**: Parametrize all six error kinds; patch `subprocess.run`; call `send_notification(kind, error)`.
**Expected**: Titles exactly match matrix (`Koe already running`, `Koe focus required`, `Koe dependency issue`, `Koe audio error`, `Koe transcription error`, `Koe insertion error`), and none equals plain `Koe`.
**Discriminating power**: Fails implementations that collapse all error titles to generic `Koe`.
**Invariant**: I2 plus AC3 subsystem clarity.
**Allowed variation**: Internal helper composition may change.
**Assertion scope rationale**: Title string is the user-visible subsystem categorization contract.
**Fragility check**: No assertions on punctuation outside specified titles.

---

#### T6N-04: Error fallback matrix is exact when `error is None` on error kinds

**Contract**: For error kinds with `error=None`, static fallback message is returned.
**Setup**: Parametrize six error kinds with `error=None`; patch `subprocess.run`; call `send_notification(kind)`.
**Expected**: Message equals exact fallback from matrix (`Another Koe invocation is active.`, `No focused window is available.`, `A required dependency is missing.`, `Microphone capture failed.`, `Transcription failed.`, `Text insertion failed.`).
**Discriminating power**: Fails empty-string or derived-message fallbacks.
**Invariant**: I2 and fallback policy in design section.
**Allowed variation**: How helper is called is not asserted.
**Assertion scope rationale**: Message argument is minimal observable fallback proof.
**Fragility check**: No check of internal helper call count.

---

#### T6N-05: Notification transport failures are swallowed for all 10 kinds

**Contract**: `send_notification` never raises under backend failure.
**Setup**: Parametrize all 10 `NotificationKind` values; patch `subprocess.run(side_effect=RuntimeError('backend down'))`; call `send_notification` (with valid error payload for error kinds).
**Expected**: No exception; function returns `None`.
**Discriminating power**: Fails any implementation that lets subprocess exceptions escape.
**Invariant**: I1 and AC4.
**Allowed variation**: Exception subclass caught may vary; behavior must remain non-raising.
**Assertion scope rationale**: Absence of raise is the contract itself.
**Fragility check**: Does not bind to stderr/stdout transport details.

---

### `outcome_to_exit_code` and `main`

Design references: `...notify-exit-semantics.md:128`, `:138`, `:224`
Depends on: `PipelineOutcome` and `ExitCode` literals

#### T6M-01: Exit mapping is total over all 9 pipeline outcomes

**Contract**: Every `PipelineOutcome` maps deterministically to one `ExitCode`.
**Setup**: Parametrize all outcomes and expected code.
**Expected**: Exact mapping table from design.
**Discriminating power**: Fails omissions, wrong code values, or accidental remaps.
**Invariant**: I5.
**Allowed variation**: Implementation style (`match` vs mapping dict) is not constrained.
**Assertion scope rationale**: Input-output table equality is minimum totality proof.
**Fragility check**: No assertions on branch internals.

---

#### T6M-02: Uncaught exception path exits directly with code 2

**Contract**: `main` catches unexpected exceptions and calls `sys.exit(2)`.
**Setup**: Patch `run_pipeline` to raise `Exception`; patch `sys.exit`.
**Expected**: `sys.exit` called with `2`; `outcome_to_exit_code` bypassed.
**Discriminating power**: Fails implementations that leak exceptions or incorrectly map through outcome table.
**Invariant**: main exception-to-exit contract.
**Allowed variation**: Exception message text.
**Assertion scope rationale**: `sys.exit(2)` is the only observable contract output.
**Fragility check**: Avoid asserting full traceback text.

---

### `run_pipeline` Section-6 dispatch semantics

Design references: `...notify-exit-semantics.md:152`, `:194`, `:213`
Depends on: stage contract tests from prior sections; these tests focus only on notification dispatch and order.

#### T6M-03a..T6M-03i: Every defined branch dispatches correct `(kind, error?)`

**Contract**: Dispatch matrix in design is exact across all terminal branches and no-speech branches.
**Setup**: One test per branch using existing patch stack pattern in `tests/test_main.py`:
- T6M-03a preflight dependency error -> `send_notification('error_dependency', dependency_error)`
- T6M-03b lock contention -> `send_notification('already_running', already_running_error)`
- T6M-03c focus gate failure -> `send_notification('error_focus', focus_error)`
- T6M-03d audio capture error -> `send_notification('error_audio', audio_error)`
- T6M-03e transcription error -> `send_notification('error_transcription', transcription_error)`
- T6M-03f insertion error -> `send_notification('error_insertion', insertion_error)`
- T6M-03g audio empty -> terminal `send_notification('no_speech')`
- T6M-03h transcription empty -> terminal `send_notification('no_speech')`
- T6M-03i success -> terminal `send_notification('completed')`
**Expected**: Exact kind and exact error object identity on error paths; lifecycle kinds omit error arg.
**Discriminating power**: Fails wrong-kind wiring, dropped error payloads, or generic error dispatch.
**Invariant**: I6, dispatch matrix rows.
**Allowed variation**: Non-terminal intermediate notifications can exist only where specified by matrix.
**Assertion scope rationale**: Kind + error tuple is minimum proof of branch semantics.
**Fragility check**: Do not assert unrelated non-terminal mock calls in branch-specific tests.

---

#### T6M-04a: `recording_started` dispatch occurs before `capture_audio`

**Contract**: Recording notification precedes capture invocation.
**Setup**: `events` list; `send_notification` side_effect appends `notify:<kind>`; `capture_audio` side_effect appends `capture_audio`.
**Expected**: `events.index('notify:recording_started') < events.index('capture_audio')`.
**Discriminating power**: Fails late notification implementations.
**Invariant**: I7.
**Allowed variation**: Additional pre-record events allowed.
**Assertion scope rationale**: Relative ordering is the required behavior.
**Fragility check**: No full sequence equality assertion.

---

#### T6M-04b: `processing` dispatch occurs before `transcribe_audio`

**Contract**: Processing notification precedes transcription invocation.
**Setup**: existing ordering pattern test.
**Expected**: `notify:processing` index is before `transcribe` index.
**Discriminating power**: Fails late processing notification implementations.
**Invariant**: I8.
**Allowed variation**: Other events may interleave if they do not violate ordering.
**Assertion scope rationale**: Relative ordering only.
**Fragility check**: Avoid exact full event timeline checks.

---

#### T6M-05: Success path notification sequence is exactly three kinds in order

**Contract**: Success dispatch sequence equals `['recording_started', 'processing', 'completed']`.
**Setup**: Full success-path run; inspect `notify_mock.call_args_list`.
**Expected**: Exact equality with three-element list.
**Discriminating power**: Fails missing completion or extra terminal notifications.
**Invariant**: dispatch ordering invariant #3.
**Allowed variation**: Internal stage implementation details.
**Assertion scope rationale**: Full sequence is explicitly contractual for success path.
**Fragility check**: Scoped to success path only; does not apply to error-path tests.

---

### Static fixture contracts

Design reference: `...notify-exit-semantics.md:457`

#### T6SF-01: `send_notification` callable signature remains stable

**Contract**: Public callable type remains compatible with `Callable[[NotificationKind], None]`.
**Setup**: New static fixture file `tests/section6_static_fixtures.py`; assign function to typed callable.
**Expected**: Pyright passes.
**Discriminating power**: Fails signature drift on parameter/return contract.

---

#### T6SF-02: `outcome_to_exit_code` callable signature remains stable

**Contract**: Callable type remains `Callable[[PipelineOutcome], ExitCode]`.
**Setup**: Same static fixture file.
**Expected**: Pyright passes.
**Discriminating power**: Fails signature drift that would break callers.

## Requirement Traceability

| Requirement | Source | Proved By Contract | Proved By Test |
|-------------|--------|--------------------|----------------|
| AC1 lifecycle states are visible | `spec.md:95` | lifecycle payload + lifecycle dispatch contracts | T6N-01, T6M-03g, T6M-03h, T6M-03i, T6M-05 |
| AC2 notifications map to clear phases | `spec.md:96` | dispatch matrix + ordering invariants | T6M-03a..T6M-03i, T6M-04a, T6M-04b, T6M-05 |
| AC3 error notifications identify subsystem + preserve context | `spec.md:97` | error title/message contracts | T6N-02, T6N-03, T6N-04, T6M-03a..T6M-03f |
| AC4 emission failures do not crash runtime | `spec.md:99` | non-raising transport contract | T6N-05 |
| Exit semantics remain deterministic | section-6 design `:224` | outcome and exception mapping contracts | T6M-01, T6M-02 |

## What Is NOT Tested (and Why)

- Notification desktop rendering style and compositor behavior: out of API scope; only subprocess args are contractual.
- Internals of audio/transcription/insertion algorithms: validated by Sections 3-5 tests; Section 6 only asserts dispatch and user-facing signaling.
- Alternative notification backends (D-Bus/Wayland): explicitly out of M1 scope.

## Test Execution Order

1. `T6SF-*` static fixtures (fast signature drift detection under `make typecheck`)
2. `T6N-*` notification payload + non-raising transport (isolated, fast)
3. `T6M-01` and `T6M-02` exit semantics (small surface)
4. `T6M-03*` branch dispatch semantics
5. `T6M-04*` ordering invariants
6. `T6M-05` success-path exact sequence

If groups 1-2 fail, later pipeline-level results are not trustworthy for Section 6 contract conformance.

## Design Gaps

None. The approved Section 6 design is testable end-to-end at the API-contract level.
