---
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 5: Insertion and Clipboard Safety"
research_source: thoughts/projects/2026-02-20-koe-m1/working/section-5-research.md
test_spec_source: thoughts/projects/2026-02-20-koe-m1/working/section-5-test-spec.md
design_source: thoughts/design/2026-02-20-koe-m1-section-5-api-design.md
---

# Koe M1 Section 5 Implementation Plan

## Overview

Implement Section 5 only: replace the text-branch handoff sentinel with real insertion orchestration, add `insert.py` clipboard/paste APIs, and preserve cleanup invariants.
This plan is test-first and bounded to Section 5 acceptance criteria in `thoughts/projects/2026-02-20-koe-m1/spec.md:82` through `thoughts/projects/2026-02-20-koe-m1/spec.md:87`.

## Current State Analysis

- Section 5 runtime is currently unimplemented: `src/koe/insert.py` is a stub (`src/koe/insert.py:1`).
- `run_pipeline` currently raises `NotImplementedError("Section 5 handoff: insertion")` for transcription `kind == "text"` (`src/koe/main.py:102`).
- Type/config contracts for Section 5 already exist (`src/koe/types.py:79`, `src/koe/types.py:108`, `src/koe/types.py:143`, `src/koe/config.py:17`).
- Cleanup ordering already exists and must remain unchanged: artifact cleanup in inner `finally`, lock release in outer `finally` (`src/koe/main.py:103`, `src/koe/main.py:106`).
- Existing tests currently encode sentinel behavior and must be updated during Section 5 integration (`tests/test_main.py:267`, `tests/test_main.py:307`, `tests/test_main.py:420`, `tests/test_main.py:472`).

## Desired End State

Section 5 acceptance criteria from `thoughts/projects/2026-02-20-koe-m1/spec.md:82` through `thoughts/projects/2026-02-20-koe-m1/spec.md:87` are fully satisfied:

1. Insertion runs as mandatory `backup -> write -> paste -> restore` sequence through `insert_transcript_text`.
2. Text transcription branch in `main.py` calls insertion and returns `success` on insertion success.
3. Insertion failures (including restore-after-paste failure) map to `error_insertion` notification and outcome.
4. Clipboard backup/restore uses `ClipboardState.content: str | None` semantics for text-only M1 guarantee.
5. Existing cleanup invariants remain intact for both insertion success and insertion failure branches.

Verification bundle:

```bash
make lint && make typecheck && make test
```

## Traceability

| Requirement | Source | Test Spec ID | Planned Phase |
|-------------|--------|--------------|---------------|
| AC1: insertion uses clipboard write + simulated paste | `thoughts/projects/2026-02-20-koe-m1/spec.md:82` | T-01, T-03, T-12, T-14 | Phase 2, Phase 4 |
| AC2: insertion path integrated into text branch | `thoughts/projects/2026-02-20-koe-m1/spec.md:83` | T-19 | Phase 3, Phase 5 |
| AC3: backup before write/paste and restore on success path | `thoughts/projects/2026-02-20-koe-m1/spec.md:84` | T-03, T-08, T-16, T-17 | Phase 2, Phase 4 |
| AC4: explicit insertion failure path + cleanup still runs | `thoughts/projects/2026-02-20-koe-m1/spec.md:85` | T-04, T-05, T-06, T-10, T-13, T-15, T-18, T-20, T-21 | Phase 2, Phase 3, Phase 4, Phase 5 |
| AC5: restore failure after paste surfaced explicitly | `thoughts/projects/2026-02-20-koe-m1/spec.md:86` | T-07, T-18, T-20 | Phase 2, Phase 4, Phase 5 |
| AC6: text-only clipboard guarantee (`None` for non-text) | `thoughts/projects/2026-02-20-koe-m1/spec.md:87` | T-09, T-17 | Phase 2, Phase 4 |

### Key Discoveries

- Section 5 API design is approved and complete; no additional API design phase is required (`thoughts/design/2026-02-20-koe-m1-section-5-api-design.md:66`).
- Section 5 requires no type-surface expansion; existing unions and errors are sufficient (`src/koe/types.py:83`, `src/koe/types.py:136`).
- `run_pipeline` integration is a local replacement of the sentinel branch and must preserve both existing `finally` blocks (`src/koe/main.py:90`, `src/koe/main.py:103`).
- Four sentinel-era tests must be migrated atomically with `main.py` integration to avoid false-red suite state (`tests/test_main.py:298`, `tests/test_main.py:336`, `tests/test_main.py:450`, `tests/test_main.py:502`).

## What We're NOT Doing

- No Section 6 notification-copy redesign; Section 5 only ensures correct notification kind and payload routing from `main.py`.
- No binary clipboard round-trip restoration; M1 remains text-only (`ClipboardState.content = None` for non-text).
- No changes to Section 4 transcription behavior or noise-token policy.
- No platform expansion beyond Linux/X11 tooling (`xclip`, `xdotool`).
- No daemon/persistent process behavior.

## Implementation Approach

Test-first delivery with strict section scope:

1. `/test-implementer` writes Section 5 failing tests from the approved test spec.
2. `/implement-plan` implements `src/koe/insert.py` APIs exactly per design contracts.
3. `/implement-plan` replaces Section 5 sentinel in `main.py` and updates orchestration behavior.
4. Existing sentinel-era `test_main.py` cases are updated in the same integration phase as `main.py` code change.

Design references applied directly:

- Public Section 5 API signatures and order contract (`thoughts/design/2026-02-20-koe-m1-section-5-api-design.md:66` through `thoughts/design/2026-02-20-koe-m1-section-5-api-design.md:97`).
- Backup/write/paste/restore per-function semantics (`thoughts/design/2026-02-20-koe-m1-section-5-api-design.md:98` through `thoughts/design/2026-02-20-koe-m1-section-5-api-design.md:118`).
- Restore-failure propagation and text-only boundary (`thoughts/design/2026-02-20-koe-m1-section-5-api-design.md:121` through `thoughts/design/2026-02-20-koe-m1-section-5-api-design.md:127`).
- `main.py` integration contract replacing sentinel branch (`thoughts/design/2026-02-20-koe-m1-section-5-api-design.md:131` through `thoughts/design/2026-02-20-koe-m1-section-5-api-design.md:147`).

## Perspectives Synthesis

**Alignment**

- Keep Section 5 changes scoped to `src/koe/insert.py`, `src/koe/main.py`, `tests/test_insert.py`, and `tests/test_main.py`.
- Enforce exact stage order and short-circuit behavior in `insert_transcript_text`.
- Preserve existing cleanup ordering in `run_pipeline` while replacing only the text-branch sentinel.
- Make test migration explicit for existing sentinel tests so suite stays trustworthy.

**Divergence (resolved in this plan)**

- Whether Section 5 should modify `notify.py` for richer insertion error rendering: resolved to no Section 5 `notify.py` changes; Section 5 proof focuses on routing kind/payload to `send_notification`, with wording/rendering still Section 6 scope.
- How to classify backup non-text clipboard vs operational failure: resolved as design-conformant behavior where non-text/no-text maps to `Ok({"content": None})`, and execution/parsing failures map to `Err(InsertionError)`.

**Key perspective contributions**

- DX Advocate: phase decomposition must prevent a long red period; migrate stale sentinel tests in the integration phase.
- Architecture Purist: no new types or modules; one concern per file with optional private helper(s) for insertion error shaping.
- Validation Strategist: explicit red-first tests for T-01..T-22, with phase-level command gates.
- Security Auditor: strict subprocess list-arg usage and explicit stage-labelled insertion errors.
- Correctness Guardian: enforce exact payload contracts (`category`, prefixes, `transcript_text`) and cleanup invariants under success/failure.

## Phase Ownership

| Phase | Owner | Responsibility |
|-------|-------|---------------|
| Phase 1-3 | `/test-implementer` | Write and migrate Section 5 tests/contracts |
| Phase 4-6 | `/implement-plan` | Implement Section 5 runtime code to satisfy tests |

## Phase 1: Section 5 Static Contract Fixture (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 5 static contract fixtures`

### Overview

Add static narrowing proofs for Section 5 return contracts before runtime implementation begins.

### Changes Required

#### 1. Add static fixture file
**File**: `tests/section5_static_fixtures.py` (new)
**Changes**:
- prove narrowing over `Result[None, InsertionError]`
- prove `ClipboardState.content` narrowing (`str` vs `None`)

```python
def t01_insert_result_narrowing(result: Result[None, InsertionError]) -> None:
    if result["ok"] is True:
        assert_type(result["value"], None)
    else:
        assert_type(result["error"], InsertionError)
```

### Success Criteria

#### Validation (required)

- [x] `tests/section5_static_fixtures.py` exists and is checked by Pyright.
- [x] Fixture verifies Section 5 typed narrowing obligations.

#### Standard Checks

- [x] `uv run ruff check tests/section5_static_fixtures.py`
- [x] `uv run pyright` (red is acceptable before implementation phases)

**Implementation Note**: Proceed when failures are attributable to unimplemented Section 5 runtime, not type-contract ambiguity.

---

## Phase 2: Insert API Contract Tests (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 5 insert api contract tests`

### Overview

Create `tests/test_insert.py` implementing T-01..T-18 from the approved Section 5 test spec.

### Changes Required

#### 1. Add insert API unit contract test file
**File**: `tests/test_insert.py` (new)
**Changes**:
- implement T-01..T-07 for `insert_transcript_text`
- implement T-08..T-11 for `backup_clipboard_text`
- implement T-12..T-13 for `write_clipboard_text`
- implement T-14..T-15 for `simulate_paste`
- implement T-16..T-18 for `restore_clipboard_text`

```python
def test_insert_transcript_text_enforces_stage_order() -> None:
    events: list[str] = []
    # patch helpers with side_effect appends
    assert events == [
        "backup_clipboard_text",
        "write_clipboard_text",
        "simulate_paste",
        "restore_clipboard_text",
    ]
```

#### 2. Encode required insertion error prefix and payload checks
**File**: `tests/test_insert.py`
**Changes**:
- assert required prefixes from design for backup/write/paste/restore errors
- assert `error["transcript_text"] == input_transcript_text` on all `Err` paths

### Success Criteria

#### Validation (required)

- [x] T-01..T-18 exist and fail red before runtime implementation.
- [x] Tests assert short-circuit rules and no forbidden downstream calls.
- [x] Tests enforce `InsertionError` payload contract (`category`, prefix, `transcript_text`).

#### Standard Checks

- [x] `uv run ruff check tests/test_insert.py`
- [x] `uv run pytest tests/test_insert.py` (expected red before Phase 4)

**Implementation Note**: Keep assertions on observable contracts; avoid brittle full-command-string expectations where contract only requires config-driven key chord.

---

## Phase 3: `main.py` Section 5 Integration Tests (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 5 main integration tests and retire handoff sentinels`

### Overview

Add T-19..T-22 in `tests/test_main.py` and migrate/remove sentinel-era `NotImplementedError` expectations.

### Changes Required

#### 1. Add Section 5 integration tests
**File**: `tests/test_main.py`
**Changes**:
- T-19: text transcription + insertion success => `success` + `completed`
- T-20: insertion `Err` => `error_insertion` + payload routed to notification
- T-21: cleanup ordering invariant preserved on insertion success/failure
- T-22: pre-Section-5 ordering remains (`processing` before `transcribe`; insertion after text result)

#### 2. Migrate sentinel-era tests
**File**: `tests/test_main.py`
**Changes**:
- replace assertions that expect `NotImplementedError("Section 5 handoff: insertion")`
- align updated tests with real insertion integration behavior

### Success Criteria

#### Validation (required)

- [x] T-19..T-22 exist and fail red before implementation.
- [x] No remaining active assertions depend on Section 5 sentinel exception.
- [x] Cleanup ordering is asserted under both insertion success and insertion error paths.

#### Standard Checks

- [x] `uv run ruff check tests/test_main.py`
- [x] `uv run pytest tests/test_main.py` (expected red before Phase 5)

**Implementation Note**: This phase is test-only; no runtime code edits.

---

## Phase 4: Implement `src/koe/insert.py` APIs (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: implement section 5 insertion and clipboard apis`

### Overview

Replace `insert.py` stub with the approved Section 5 public API and make T-01..T-18 pass.

### Changes Required

#### 1. Implement Section 5 insert APIs
**File**: `src/koe/insert.py`
**Changes**:
- add `insert_transcript_text(transcript_text, config, /)`
- add `backup_clipboard_text(transcript_text, /)`
- add `write_clipboard_text(text, transcript_text, /)`
- add `simulate_paste(config, transcript_text, /)`
- add `restore_clipboard_text(state, transcript_text, /)`
- convert subprocess failures to `Err(InsertionError)` with required stage prefixes

```python
def insert_transcript_text(transcript_text: str, config: KoeConfig, /) -> Result[None, InsertionError]:
    if transcript_text.strip() == "":
        return {"ok": False, "error": {...}}
    # backup -> write -> paste -> restore
    return {"ok": True, "value": None}
```

#### 2. Keep behavior contracts exact
**File**: `src/koe/insert.py`
**Changes**:
- `restore` failure after successful paste must return `Err`, not `Ok`
- `state["content"] is None` in restore must no-op and return `Ok(None)`
- backup non-text/no-text path must return `Ok({"content": None})`

### Success Criteria

#### Validation (required)

- [x] T-01..T-18 pass.
- [x] All `Err` arms return `InsertionError` with required prefix and original transcript text.
- [x] No expected-failure path raises exceptions.

#### Standard Checks

- [x] `uv run pytest tests/test_insert.py`
- [x] `uv run pyright`
- [x] `uv run ruff check src/koe/insert.py tests/test_insert.py`

**Implementation Note**: Keep insert module procedural and flat; no peer-module orchestration logic.

---

## Phase 5: Replace Section 5 Sentinel in `main.py` (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: wire section 5 insertion into run_pipeline`

### Overview

Replace the text-branch sentinel with insertion integration per approved design.

### Changes Required

#### 1. Wire insertion call in text branch
**File**: `src/koe/main.py`
**Changes**:
- import `insert_transcript_text`
- replace sentinel with insertion result handling
- on insertion `Err`: send `error_insertion`, return `error_insertion`
- on insertion `Ok`: send `completed`, return `success`

```python
insertion_result = insert_transcript_text(transcription_result["text"], config)
if insertion_result["ok"] is False:
    send_notification("error_insertion", insertion_result["error"])
    return "error_insertion"
send_notification("completed")
return "success"
```

#### 2. Preserve cleanup invariants exactly
**File**: `src/koe/main.py`
**Changes**:
- keep inner/outer `finally` structure unchanged
- verify artifact cleanup and lock release still run on insertion success/failure

### Success Criteria

#### Validation (required)

- [x] T-19..T-22 pass.
- [x] Existing non-Section-5 pipeline behaviors remain unchanged.
- [x] Cleanup ordering remains artifact removal before lock release.

#### Standard Checks

- [x] `uv run pytest tests/test_main.py`
- [x] `uv run pyright`
- [x] `uv run ruff check src/koe/main.py tests/test_main.py`

**Implementation Note**: Keep Section 5 integration branch explicit; do not refactor broader orchestration in this section.

---

## Phase 6: Section 5 Regression Gate (Green)

**Owner**: `/implement-plan`
**Commit**: `test: verify section 5 contracts and full regression gate`

### Overview

Run full quality gates and confirm Section 5 integration does not regress prior sections.

### Changes Required

#### 1. Execute full validation suite
**Files**: none (validation phase)
**Changes**:

```bash
uv run pytest tests/test_insert.py tests/test_main.py tests/test_types.py
uv run pyright
uv run ruff check src/ tests/
make lint && make typecheck && make test
```

### Success Criteria

#### Validation (required)

- [x] All Section 5 tests (T-01..T-22) pass.
- [x] Full suite remains green with zero lint/type regressions.
- [x] No sentinel-era Section 5 exception assertions remain active.

#### Standard Checks

- [x] `make lint`
- [x] `make typecheck`
- [x] `make test`

**Implementation Note**: If failures appear outside Section 5 scope, apply minimal compatible fixes without widening section scope.

## Testing Strategy

Test phases land first. Implementation phases make those tests pass.

### Tests (written by `/test-implementer`)

- `tests/section5_static_fixtures.py` for static narrowing and contract closure.
- `tests/test_insert.py` for insert API contracts T-01..T-18.
- `tests/test_main.py` updates for integration contracts T-19..T-22 and sentinel-test migration.

### Additional Validation (implementation phases)

- `pyright` for union narrowing and signature compatibility.
- `ruff` for import/order/style consistency.
- full pytest and make gates for regression confidence.

### Manual Testing Steps

1. Run `make run` from an X11 terminal session and verify successful spoken text appears at terminal input.
2. Verify clipboard restores to prior text on insertion success.
3. Verify insertion failure path returns explicit notification and process exits cleanly.

Reason manual verification is required: AC2 targets real terminal insertion behavior in the environment, which unit mocks cannot fully prove.

## Execution Graph

**Phase Dependencies:**

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> Phase 6
```

| Phase | Depends On | Can Parallelize With |
|-------|------------|---------------------|
| 1 | - | - |
| 2 | 1 | - |
| 3 | 1 | 2 (partial; separate test files, but both red-phase outputs feed implementation) |
| 4 | 2,3 | - |
| 5 | 4 | - |
| 6 | 4,5 | - |

**Parallel Execution Notes**

- Phase 2 and Phase 3 can be authored in parallel after Phase 1, but both must finish before implementation begins.
- Phase 4 and Phase 5 are intentionally sequential to keep behavior changes reviewable and avoid cross-file merge ambiguity.
- Keep one validated commit per phase.

## References

- Section 5 requirements: `thoughts/projects/2026-02-20-koe-m1/spec.md:76`
- Section 5 research: `thoughts/projects/2026-02-20-koe-m1/working/section-5-research.md:36`
- Section 5 test specification: `thoughts/projects/2026-02-20-koe-m1/working/section-5-test-spec.md:30`
- Section 5 API design: `thoughts/design/2026-02-20-koe-m1-section-5-api-design.md:57`
- Source brief insertion strategy: `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:82`
