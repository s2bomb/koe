---
title: "Section 5 Insertion and Clipboard Safety Test Specification"
date: 2026-02-20
status: approved
design_source: "thoughts/design/2026-02-20-koe-m1-section-5-api-design.md"
spec_source: "thoughts/projects/2026-02-20-koe-m1/spec.md"
research_source: "thoughts/projects/2026-02-20-koe-m1/working/section-5-research.md"
project_section: "Section 5: Insertion and Clipboard Safety"
---

# Test Specification: Section 5 Insertion and Clipboard Safety

## Purpose

This document defines the proof obligations for Section 5 contracts only: `insert.py` insertion/clipboard APIs and the `main.py` text-branch orchestration integration. Every Section 5 API contract is mapped to tests, with explicit error-path coverage.

## Test Infrastructure

**Framework**: `pytest` + `typeguard`, with Pyright strict static checks.
**Test location**: `tests/test_insert.py` (new), updates to `tests/test_main.py`, and optional static fixture in `tests/section5_static_fixtures.py`.
**Patterns to follow**:
- Orchestration stage short-circuit + downstream `assert_not_called()` (`tests/test_main.py:116`).
- Ordered call/event assertions via side effects (`tests/test_main.py:198`).
- Notification sequence checks via `call_args_list` (`tests/test_main.py:267`).
- Subprocess boundary mocking with deterministic side effects (`tests/test_window.py:12`, `tests/test_window.py:53`).
- Runtime TypedDict shape checks for error contracts (`tests/test_types.py:123`, `tests/test_types.py:140`).
**Utilities available**: local helper factories in each test file (no `conftest.py`) (`tests/test_window.py:12`, `tests/test_hotkey.py:9`).
**Run command**: `uv run pytest tests/test_insert.py tests/test_main.py` (full gate: `make lint && make typecheck && make test`).

## API Surface

Contracts under test, extracted from `thoughts/design/2026-02-20-koe-m1-section-5-api-design.md`:

| Contract | Signature / Rule | Design Reference | Tests |
|----------|------------------|------------------|-------|
| Insert API | `insert_transcript_text(transcript_text: str, config: KoeConfig, /) -> Result[None, InsertionError]` | `...section-5-api-design.md:66`, `...:88-97` | T-01..T-07 |
| Empty transcript rejection | `transcript_text.strip() == ""` returns `Err(InsertionError)` | `...section-5-api-design.md:89` | T-02 |
| Fixed stage order | backup -> write -> paste -> restore | `...section-5-api-design.md:90-95` | T-03 |
| Backup API | `backup_clipboard_text(transcript_text: str, /) -> Result[ClipboardState, InsertionError]` with `str | None` semantics | `...section-5-api-design.md:70`, `...:98-104` | T-08..T-11 |
| Write API | `write_clipboard_text(text: str, transcript_text: str, /) -> Result[None, InsertionError]` | `...section-5-api-design.md:74`, `...:105-108` | T-12, T-13 |
| Paste API | `simulate_paste(config: KoeConfig, transcript_text: str, /) -> Result[None, InsertionError]` using config key chord only | `...section-5-api-design.md:78`, `...:109-112` | T-14, T-15 |
| Restore API | `restore_clipboard_text(state: ClipboardState, transcript_text: str, /) -> Result[None, InsertionError]` | `...section-5-api-design.md:82`, `...:113-118` | T-16..T-18 |
| Error payload contract | all insertion errors use category/prefix/transcript_text fields | `...section-5-api-design.md:149-160` | T-04, T-10, T-13, T-15, T-18 |
| Main integration | text arm calls insertion; error -> `error_insertion`; success -> `completed` + `success` | `...section-5-api-design.md:131-142`, `...:145-148` | T-19..T-22 |
| Clipboard restore failure surfaced | restore failure after paste is not success | `...section-5-api-design.md:125-127` | T-07, T-20 |

## Proof Obligations

### `insert_transcript_text(transcript_text, config, /) -> Result[None, InsertionError]`

#### T-01: returns `Ok(None)` only when all four stages succeed

**Contract**: success requires backup+write+paste+restore all succeed.
**Setup**: Patch stage helpers to return `Ok` in sequence.
**Expected**: result is `{"ok": True, "value": None}`.
**Discriminating power**: fails if implementation returns success after partial completion.
**Invariant**: success implies full stage completion.
**Allowed variation**: implementation may use different subprocess flags if observable contract holds.
**Assertion scope rationale**: assert only discriminator/value and stage completion, not subprocess command internals.
**Fragility check**: avoid asserting exact helper call kwargs beyond contract-required inputs.

#### T-02: rejects empty/whitespace transcript at API edge

**Contract**: empty stripped transcript returns insertion error.
**Setup**: call with `""`, `"   "`, and `"\n\t"` (parametrized).
**Expected**: `Err(InsertionError)` with `category="insertion"`; message starts `"clipboard write failed:"` or a dedicated empty-input insertion message if design is updated.
**Discriminating power**: catches implementations that attempt clipboard mutation on empty input.
**Invariant**: blank transcript never reaches mutation stages.
**Allowed variation**: exact non-prefix wording can vary if still actionable and stage-labelled.
**Assertion scope rationale**: enforce failure arm and insertion category; avoid locking whole message body.
**Fragility check**: do not assert exact punctuation/capitalization.

#### T-03: enforces stage ordering backup -> write -> paste -> restore

**Contract**: fixed order is mandatory.
**Setup**: patch helpers with side effects that append to `events`.
**Expected**: exact sequence `[
"backup_clipboard_text", "write_clipboard_text", "simulate_paste", "restore_clipboard_text"
]`.
**Discriminating power**: catches reordering bugs (for example paste before backup).
**Invariant**: backup always precedes write/paste.
**Allowed variation**: internal helper implementation may change; ordering contract cannot.
**Assertion scope rationale**: order list is the smallest observable proof of sequencing.
**Fragility check**: do not include unrelated events in equality assertion.

#### T-04: backup-stage failure propagates as insertion error and short-circuits

**Contract**: any stage failure returns `Err(InsertionError)` immediately.
**Setup**: patch backup to return `Err` with backup prefix; patch downstream helpers as spies.
**Expected**: returned error forwarded unchanged; write/paste/restore not called.
**Discriminating power**: catches swallow-and-continue implementations.
**Invariant**: no downstream mutation after failed prerequisite stage.
**Allowed variation**: error message suffix text may differ.
**Assertion scope rationale**: assert short-circuit + typed error payload.
**Fragility check**: avoid asserting full stack traces or stderr string formatting.

#### T-05: write-stage failure propagates and blocks paste/restore

**Contract**: write failure is surfaced; paste does not execute.
**Setup**: backup returns `Ok`; write returns `Err`; paste/restore patched as spies.
**Expected**: `Err` with insertion category and write prefix; paste/restore uncalled.
**Discriminating power**: catches implementations that keep going after write failure.

#### T-06: paste-stage failure propagates and blocks restore

**Contract**: paste failure returns insertion error; restore not attempted.
**Setup**: backup/write `Ok`; paste `Err`; restore spy.
**Expected**: `Err` with prefix `"paste simulation failed:"`; restore not called.
**Discriminating power**: catches accidental restore execution on failed paste branch.

#### T-07: restore-stage failure after successful paste is surfaced as failure

**Contract**: restore failure after paste is never silent success.
**Setup**: backup/write/paste all `Ok`; restore `Err` with restore prefix.
**Expected**: top-level result is `Err` restore error (not success).
**Discriminating power**: catches implementations that mark run successful once paste happens.

### `backup_clipboard_text(transcript_text, /) -> Result[ClipboardState, InsertionError]`

#### T-08: returns previous text when textual clipboard content exists

**Contract**: readable text clipboard becomes `ClipboardState.content: str`.
**Setup**: mock subprocess read path with successful text output.
**Expected**: `Ok({"content": "<text>"})`.
**Discriminating power**: catches implementations that collapse all reads to `None`.

#### T-09: returns `content=None` for non-text/empty clipboard under M1 boundary

**Contract**: non-text or unavailable text clipboard maps to `None`, not error.
**Setup**: mock read path representing non-text/no-text clipboard outcome.
**Expected**: `Ok({"content": None})`.
**Discriminating power**: catches over-eager failures that convert non-text to operational errors.

#### T-10: operational backup failure returns prefixed insertion error with transcript preservation

**Contract**: command execution/parsing failure returns insertion error payload.
**Setup**: subprocess runner raises/returns failing status on backup command.
**Expected**: `Err` where `error.category == "insertion"`, message starts `"clipboard backup failed:"`, and `error.transcript_text` equals input transcript.
**Discriminating power**: catches missing transcript passthrough and wrong category/prefix.

#### T-11: backup performs no clipboard write side effects

**Contract**: backup is read-only.
**Setup**: patch subprocess and inspect invoked command arguments.
**Expected**: only read command(s) issued; no write invocation.
**Discriminating power**: catches accidental overwrite during backup step.

### `write_clipboard_text(text, transcript_text, /) -> Result[None, InsertionError]`

#### T-12: writes provided text to CLIPBOARD selection on success

**Contract**: successful write returns `Ok(None)` and uses passed `text`.
**Setup**: patch subprocess write command to success; call with distinct `text` and `transcript_text`.
**Expected**: success arm; invoked command payload carries `text` argument, not `transcript_text` fallback.
**Discriminating power**: catches wrong-source payload wiring.

#### T-13: write command failure returns `clipboard write failed:` error contract

**Contract**: write failure maps to insertion error with required prefix and transcript preservation.
**Setup**: failing write subprocess result/exception.
**Expected**: `Err(InsertionError)` with required prefix/category/transcript field.
**Discriminating power**: catches exception leakage and prefix drift.

### `simulate_paste(config, transcript_text, /) -> Result[None, InsertionError]`

#### T-14: uses config key chord (`paste_key_modifier` + `paste_key`) as sole source

**Contract**: paste key simulation must be config-driven.
**Setup**: override config with uncommon values (for example `alt` + `Insert`), patch subprocess.
**Expected**: successful result and command arguments reflect override values exactly.
**Discriminating power**: catches hard-coded `ctrl+v` behavior.

#### T-15: paste simulation failure returns `paste simulation failed:` error contract

**Contract**: simulation errors are converted to insertion errors.
**Setup**: simulate xdotool failure.
**Expected**: `Err` with required prefix/category/transcript field.
**Discriminating power**: catches swallowed xdotool failures.

### `restore_clipboard_text(state, transcript_text, /) -> Result[None, InsertionError]`

#### T-16: restores exact prior text when `state.content` is `str`

**Contract**: restore writes exact previous text back.
**Setup**: `state={"content": "prior text"}` with successful write path.
**Expected**: `Ok(None)` and write payload exactly equals `"prior text"`.
**Discriminating power**: catches accidental normalization/mutation of restored clipboard text.

#### T-17: no-op success when `state.content is None`

**Contract**: `None` state performs no write and still succeeds.
**Setup**: `state={"content": None}` with subprocess spy.
**Expected**: `Ok(None)` and zero write subprocess calls.
**Discriminating power**: catches implementations that write literal `"None"` or fail no-text restore.

#### T-18: restore write failure returns `clipboard restore failed:` error contract

**Contract**: restore failures produce insertion error and do not raise.
**Setup**: `state.content` as string with failing restore write path.
**Expected**: `Err` with required prefix/category/transcript field.
**Discriminating power**: catches silent restore failures.

### `run_pipeline(config, /) -> PipelineOutcome` Section 5 integration branch

#### T-19: text transcription calls insertion and returns success path when insertion succeeds

**Contract**: text arm integrates insertion, emits completion notification, returns `"success"`.
**Setup**: patch pre-Section-5 stages to reach text arm; patch `insert_transcript_text` to `Ok(None)`.
**Expected**: `insert_transcript_text` called with transcription text + config; `send_notification("completed")`; outcome `"success"`.
**Discriminating power**: catches stale `NotImplementedError` handoff and missing insertion invocation.

#### T-20: insertion error maps to `error_insertion` notification and pipeline outcome

**Contract**: insertion failure path is explicit and actionable.
**Setup**: patch insertion to return concrete `InsertionError` payload.
**Expected**: `send_notification("error_insertion", insertion_error)` and returned outcome `"error_insertion"`.
**Discriminating power**: catches wrong notification kind, dropped payload, or wrong outcome mapping.

#### T-21: cleanup invariants remain unchanged on both insertion success and insertion failure

**Contract**: artifact cleanup then lock release still run via existing `finally` structure.
**Setup**: two variants (insertion success; insertion error), event log over `remove_audio_artifact` and `release_instance_lock`.
**Expected**: both cleanup calls happen in both variants, with artifact cleanup observed before lock release.
**Discriminating power**: catches integration regressions that bypass or reorder cleanup boundaries.

#### T-22: processing notification still precedes transcription and insertion integration does not alter pre-Section-5 ordering

**Contract**: Section 5 integration must not disturb prior stage ordering.
**Setup**: event list across `send_notification("processing")`, `transcribe_audio`, `insert_transcript_text`.
**Expected**: `processing` occurs before transcription; insertion occurs only after text transcription returns.
**Discriminating power**: catches orchestration-order regressions introduced by Section 5 merge.

## Requirement Traceability

| Requirement | Source | Proved By Contract | Proved By Tests |
|-------------|--------|--------------------|-----------------|
| AC1: insertion uses clipboard write + simulated paste | `thoughts/projects/2026-02-20-koe-m1/spec.md:82` | `insert_transcript_text` stage composition, `write_clipboard_text`, `simulate_paste` | T-01, T-03, T-12, T-14 |
| AC2: text insertion path works in target runtime contractually | `thoughts/projects/2026-02-20-koe-m1/spec.md:83` | `main.run_pipeline` text-arm insertion integration | T-19 |
| AC3: backup before write/paste, restore on successful run | `thoughts/projects/2026-02-20-koe-m1/spec.md:84` | backup/restore ordering + restore semantics | T-03, T-08, T-16, T-17 |
| AC4: insertion failure path explicit; cleanup still runs | `thoughts/projects/2026-02-20-koe-m1/spec.md:85` | insertion failure mapping and orchestration cleanup invariants | T-04, T-05, T-06, T-10, T-13, T-15, T-18, T-20, T-21 |
| AC5: restore failure after paste surfaced explicitly | `thoughts/projects/2026-02-20-koe-m1/spec.md:86` | restore-failure propagation contract in insert + main mapping | T-07, T-18, T-20 |
| AC6: text-only clipboard guarantee documented and represented as `None` | `thoughts/projects/2026-02-20-koe-m1/spec.md:87` | `ClipboardState.content: str | None` handling in backup/restore APIs | T-09, T-17 |

## What Is NOT Tested (and Why)

- Real terminal emulator paste compatibility matrix: out of API-surface scope; this spec proves contract wiring, not environment-specific UX variance.
- Binary clipboard round-trip preservation: explicitly out of M1 scope per design (`...section-5-api-design.md:29`, `...:127`).
- Notification copy wording beyond required routing/kind/payload: Section 6 scope.
- Internal subprocess argument ordering that is not contractually observable (except config key chord usage in T-14).

## Test Execution Order

1. `insert.py` unit contracts and error payload shape (T-01..T-18).
2. `main.py` Section 5 integration mapping and cleanup ordering (T-19..T-22).
3. Optional static narrowing fixture checks under `uv run pyright` (`tests/section5_static_fixtures.py`).

If group 1 fails, group 2 results are not trusted.

## Design Gaps

- No blocking testability gaps in the Section 5 API design.
- Non-blocking note: T-02 assumes empty transcript maps to `InsertionError` but does not lock a specific prefix unless the implementation contract explicitly assigns one; planner should keep assertions prefix-based only where the design mandates prefixes (`backup/write/paste/restore`).

Test specification complete.

**Location**: `thoughts/projects/2026-02-20-koe-m1/working/section-5-test-spec.md`
**Summary**: 22 tests across 10 Section 5 API contracts
**Design gaps**: none blocking

Ready for planner.
