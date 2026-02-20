---
title: "Section 1 Foundations and Delivery Baseline Test Specification"
date: 2026-02-20
status: approved
design_source: "thoughts/design/2026-02-20-koe-m1-section-1-api-design.md"
spec_source: "thoughts/projects/2026-02-20-koe-m1/spec.md"
research_source: "thoughts/projects/2026-02-20-koe-m1/working/section-1-research.md"
project_section: "Section 1: Foundations and Delivery Baseline"
---

# Test Specification: Section 1 Foundations and Delivery Baseline

## Purpose

This document defines proof obligations for the Section 1 API surface only: `types.py`, `config.py`, and `main.py` invocation contracts. Every test below maps to an explicit design contract and is written to fail incorrect implementations, including explicit error-path behavior.

## Test Infrastructure

**Framework**: `pytest` with `typeguard` runtime checks, plus Pyright static checks.
**Test location**: root `tests/` directory, flat `test_<module>.py` naming.
**Patterns to follow**:
- Plain pytest `assert` style and pytest markers (`pyproject.toml:51`, Ruff `PT` rules).
- Config override pattern: `{**DEFAULT_CONFIG, "key": value}` (design doc `:324-325`, `:725-726`).
- Runtime type-shape assertions with `typeguard.check_type` (design doc `:619-636`).
- Parametrized literal mapping tests for total-coverage enum-like aliases (design doc `:643`).
**Utilities available**: none currently in repo (`tests/` and `conftest.py` absent); tests should be self-contained module tests.
**Run command**: `uv run pytest tests/` with gates `uv run pyright` and `uv run ruff check src/ tests/`.

## API Surface

Contracts under test, extracted from the design doc:

| Contract | Signature / Type | Design Reference | Tests |
|----------|-------------------|------------------|-------|
| `AudioArtifactPath` | `NewType("AudioArtifactPath", Path)` | `...api-design.md:53` | T-01 |
| `WindowId` | `NewType("WindowId", int)` | `...api-design.md:61` | T-01 |
| `Ok[T]` | `TypedDict{ok: Literal[True], value: T}` | `...api-design.md:70-77` | T-02 |
| `Err[E]` | `TypedDict{ok: Literal[False], error: E}` | `...api-design.md:79-86` | T-03 |
| `Result[T, E]` | `Ok[T] | Err[E]` discriminated union on `ok` | `...api-design.md:88-99` | T-04 |
| `HotkeyAction` | `Literal["start", "stop"]` | `...api-design.md:104-112` | T-05 |
| `FocusedWindow` | `TypedDict{window_id: WindowId, title: str}` | `...api-design.md:117-124` | T-06 |
| `WindowFocusResult` | `FocusedWindow | None` | `...api-design.md:126-135` | T-07 |
| `TranscriptionText` | `TypedDict{kind: "text", text: str}` | `...api-design.md:147-154` | T-08 |
| `TranscriptionNoSpeech` | `TypedDict{kind: "empty"}` | `...api-design.md:156-163` | T-09 |
| `TranscriptionFailure` | `TypedDict{kind: "error", error: TranscriptionError}` | `...api-design.md:165-173` | T-10 |
| `TranscriptionResult` | `TranscriptionText | TranscriptionNoSpeech | TranscriptionFailure` | `...api-design.md:175-185` | T-11 |
| `ClipboardState` | `TypedDict{content: str | None}` | `...api-design.md:190-198` | T-12 |
| `NotificationKind` | fixed literal union of 8 states | `...api-design.md:202-216` | T-13 |
| `FocusError` | `TypedDict{category: "focus", message: str}` | `...api-design.md:221-225` | T-14 |
| `AudioError` | `TypedDict{category: "audio", message: str, device: str | None}` | `...api-design.md:227-233` | T-14 |
| `TranscriptionError` | `TypedDict{category: "transcription", message: str, cuda_available: bool}` | `...api-design.md:235-241` | T-14 |
| `InsertionError` | `TypedDict{category: "insertion", message: str, transcript_text: str}` | `...api-design.md:243-252` | T-14 |
| `DependencyError` | `TypedDict{category: "dependency", message: str, missing_tool: str}` | `...api-design.md:254-260` | T-14 |
| `KoeError` | union of five error typed dicts | `...api-design.md:262-273` | T-15 |
| `PipelineOutcome` | fixed literal union of 8 outcomes | `...api-design.md:278-292` | T-16 |
| `ExitCode` | `Literal[0, 1, 2]` | `...api-design.md:295-303` | T-17 |
| `KoeConfig` | total `TypedDict` runtime config schema | `...api-design.md:332-395` | T-18 |
| `DEFAULT_CONFIG` | `Final[KoeConfig]` immutable default constants | `...api-design.md:396-414` | T-19 |
| `main()` | `() -> None`, never raises, always exits, maps unexpected to code 2 | `...api-design.md:439-447`, `:569-575` | T-20 |
| `run_pipeline(config)` | `(KoeConfig) -> PipelineOutcome`, cleanup on all paths | `...api-design.md:451-510` | T-21 |
| `outcome_to_exit_code(outcome)` | pure total mapping `PipelineOutcome -> ExitCode` | `...api-design.md:513-533` | T-22 |

## Proof Obligations

### `types.py` contracts

#### T-01: Opaque aliases reject bare primitives at type-check boundaries

**Contract**: `AudioArtifactPath` and `WindowId` are not interchangeable with bare `Path` and `int`.
**Setup**: Pyright static fixture file with positive and negative assignments.
**Expected**: Correctly wrapped values type-check; bare primitive assignment to alias-typed variable is flagged.
**Discriminating power**: Catches alias weakening to `type = Path/int` that would allow accidental misuse.
**Contract invariant**: Boundary types remain opaque to callers.
**Allowed variation**: Internal implementation may use constructors/helpers; alias identity must remain enforced.
**Assertion scope rationale**: Static assignability is the minimum direct proof for `NewType` contract.
**Fragility check**: Does not assert runtime `isinstance` identity details.

#### T-02: `Ok[T]` shape and success discriminator are enforced

**Contract**: `Ok[T]` requires `ok=True` and typed `value`.
**Setup**: `check_type` with valid `Ok[str]`; invalid case with `ok=False` in `Ok` shape.
**Expected**: Valid object accepted; invalid discriminator rejected.
**Discriminating power**: Catches non-discriminated or loosely typed success arm.
**Contract invariant**: `ok` literal is the narrowing key.
**Allowed variation**: Value payload contents may vary by `T`.
**Assertion scope rationale**: Only discriminator and required keys are asserted.
**Fragility check**: No assertion on dict key order or incidental repr.

#### T-03: `Err[E]` shape and error discriminator are enforced

**Contract**: `Err[E]` requires `ok=False` and typed `error` payload.
**Setup**: `check_type` with valid `Err[FocusError]`; invalid case with missing `error` key.
**Expected**: Valid object accepted; missing-key shape rejected.
**Discriminating power**: Catches implementations that return generic dicts without structured error payload.
**Contract invariant**: Error arm always carries a typed error value.
**Allowed variation**: Error payload subtype may vary by `E`.
**Assertion scope rationale**: Minimal key-level proof.
**Fragility check**: Avoids asserting full error message text content.

#### T-04: `Result[T, E]` narrows correctly on `result["ok"]` for both paths

**Contract**: Union is discriminated and statically narrowable in both arms.
**Setup**: Pyright static snippet branching on `result["ok"]` and accessing only valid keys per branch.
**Expected**: Accessing `value` in false branch or `error` in true branch is a type error.
**Discriminating power**: Catches union mis-definition that removes compiler-enforced handling.
**Contract invariant**: Callers must handle both outcomes.
**Allowed variation**: Branch syntax (`if` or `match`) may vary.
**Assertion scope rationale**: Narrowing behavior is the contract itself.
**Fragility check**: Does not require specific control-flow style.

#### T-05: `HotkeyAction` accepts only `"start"` and `"stop"`

**Contract**: Literal vocabulary is closed to two actions.
**Setup**: Pyright assignment checks for allowed and disallowed strings.
**Expected**: `"start"`/`"stop"` pass, any other literal fails type-check.
**Discriminating power**: Catches widening to plain `str`.
**Contract invariant**: No third hotkey state in M1.
**Allowed variation**: Producer implementation details are irrelevant.
**Assertion scope rationale**: Literal-set membership is sufficient proof.
**Fragility check**: No dependency on hotkey module internals.

#### T-06: `FocusedWindow` requires both typed fields

**Contract**: Object includes `window_id: WindowId` and `title: str`.
**Setup**: `check_type` valid dict; invalid dict missing `title`.
**Expected**: Valid shape accepted; incomplete shape rejected.
**Discriminating power**: Catches partial-window payloads that would break insertion stage assumptions.
**Contract invariant**: Focus metadata is complete when present.
**Allowed variation**: Title content unrestricted.
**Assertion scope rationale**: Required-field existence and types only.
**Fragility check**: Does not assert exact title text.

#### T-07: `WindowFocusResult` supports `None` for no-focus path

**Contract**: Type is exactly `FocusedWindow | None`.
**Setup**: `check_type` with valid `FocusedWindow` and `None`.
**Expected**: Both values are accepted.
**Discriminating power**: Catches accidental removal of `None` arm.
**Contract invariant**: No-focus is first-class data state.
**Allowed variation**: How caller converts this into notification flow.
**Assertion scope rationale**: Two-arm acceptance is minimal proof.
**Fragility check**: No assertion about downstream stage behavior.

#### T-08: `TranscriptionText` enforces text success arm schema

**Contract**: Success transcription arm has `kind="text"` and `text: str`.
**Setup**: `check_type` valid text arm and invalid missing-text case.
**Expected**: Valid shape accepted; missing text rejected.
**Discriminating power**: Catches schema drift that could break insertion contract.
**Contract invariant**: Text arm always carries text payload.
**Allowed variation**: Text content/value not semantically constrained in this layer.
**Assertion scope rationale**: Minimal arm-specific keys only.
**Fragility check**: No assumptions about transcript wording.

#### T-09: `TranscriptionNoSpeech` enforces empty arm schema

**Contract**: No-speech arm is represented by `kind="empty"` only.
**Setup**: `check_type` with `{"kind": "empty"}` and invalid payload using wrong kind.
**Expected**: Empty arm accepted; wrong literal rejected.
**Discriminating power**: Catches collapse of no-speech into generic error path.
**Contract invariant**: Empty transcription is distinct from failure.
**Allowed variation**: No extra required fields.
**Assertion scope rationale**: Literal discriminator proves semantics.
**Fragility check**: No assertion on absent optional metadata.

#### T-10: `TranscriptionFailure` carries typed error payload

**Contract**: Error arm requires `kind="error"` and `error: TranscriptionError`.
**Setup**: `check_type` valid arm and invalid wrong error category.
**Expected**: Only correctly categorized transcription error passes.
**Discriminating power**: Catches mixing unrelated error payloads.
**Contract invariant**: Failure arm remains diagnostic, not opaque string.
**Allowed variation**: `message` value varies.
**Assertion scope rationale**: Category + required keys are enough.
**Fragility check**: No exact message text match.

#### T-11: `TranscriptionResult` is exhaustively three-armed

**Contract**: Union accepts text/empty/error arms and no others.
**Setup**: Parametrized runtime `check_type` for the three valid variants plus one invalid `kind`.
**Expected**: Three valid variants accepted; unknown kind rejected.
**Discriminating power**: Catches accidental widening to free-form dict.
**Contract invariant**: Caller can exhaustively branch on `kind`.
**Allowed variation**: Arm payload contents can evolve if arm schemas remain valid.
**Assertion scope rationale**: Exhaustive discriminator coverage is minimum proof.
**Fragility check**: No ordering assumptions for union members.

#### T-12: `ClipboardState` preserves nullable text contract

**Contract**: Clipboard snapshot content may be `str` or `None` only.
**Setup**: `check_type` with string content and `None` content.
**Expected**: Both accepted.
**Discriminating power**: Catches over-tightening to non-null-only content.
**Contract invariant**: Empty/non-text snapshot is representable.
**Allowed variation**: Actual clipboard strings vary.
**Assertion scope rationale**: Nullability is the key behavioral contract.
**Fragility check**: No assertions about clipboard source.

#### T-13: `NotificationKind` literal vocabulary is closed and complete

**Contract**: Exactly eight notification literals are accepted.
**Setup**: Pyright static assignment checks for all valid literals plus one invalid literal.
**Expected**: Valid set passes; invalid literal fails.
**Discriminating power**: Catches accidental removal/renaming/widening to `str`.
**Contract invariant**: Notification API is phase/error-category stable.
**Allowed variation**: Notification rendering text stays out of scope.
**Assertion scope rationale**: Literal membership check directly proves contract.
**Fragility check**: No UI or command invocation assertions.

#### T-14: Each concrete error typed dict enforces category-specific shape

**Contract**: `FocusError`, `AudioError`, `TranscriptionError`, `InsertionError`, `DependencyError` preserve required category and fields.
**Setup**: One valid `check_type` sample per error type and one invalid sample per type missing a required key.
**Expected**: Valid shape accepted, incomplete shape rejected for each subtype.
**Discriminating power**: Catches generic error object reuse across categories.
**Contract invariant**: Each category carries diagnostic fields promised by contract.
**Allowed variation**: `message` content and optional device values.
**Assertion scope rationale**: Per-type required fields only.
**Fragility check**: No exact string checks for messages/tool names.

#### T-15: `KoeError` union narrows by `error["category"]`

**Contract**: Union discrimination by category is valid and exhaustive.
**Setup**: Pyright snippet matching on category and accessing subtype-specific fields.
**Expected**: Accessing subtype-only field in wrong branch is a type error.
**Discriminating power**: Catches weakened union that loses category-guided safety.
**Contract invariant**: Error-handling code can branch without unsafe casts.
**Allowed variation**: Branch structure may vary.
**Assertion scope rationale**: Narrowing behavior is the contract guarantee.
**Fragility check**: No runtime dependency on later stage modules.

#### T-16: `PipelineOutcome` literal set is closed to eight outcomes

**Contract**: Only documented outcomes are permitted.
**Setup**: Pyright assignment check covering all eight literals and one invalid literal.
**Expected**: Eight pass, invalid fails.
**Discriminating power**: Catches accidental outcome drift.
**Contract invariant**: Outcome vocabulary remains stable for orchestration/tests.
**Allowed variation**: Which stage produces which outcome belongs to later sections.
**Assertion scope rationale**: Literal-set test is sufficient at Section 1 scope.
**Fragility check**: No assertions on runtime pipeline internals.

#### T-17: `ExitCode` is restricted to 0, 1, 2

**Contract**: Exit code type disallows arbitrary ints.
**Setup**: Pyright assignment check for `0/1/2` plus `3` negative case.
**Expected**: `3` is rejected.
**Discriminating power**: Catches widening to plain `int`.
**Contract invariant**: Process exit space is explicitly bounded.
**Allowed variation**: Internal mapping function implementation.
**Assertion scope rationale**: Assignability is the direct proof target.
**Fragility check**: No assertion on OS process behavior.

### `config.py` contracts

#### T-18: `KoeConfig` total schema requires all fields with declared types

**Contract**: `KoeConfig` includes all required keys and literal-constrained fields.
**Setup**: `check_type(DEFAULT_CONFIG, KoeConfig)` plus negative runtime sample missing one key; Pyright negative sample assigning `"cpu"` to `whisper_device`.
**Expected**: Full shape passes; missing key and invalid literal fail.
**Discriminating power**: Catches partial configs and widened device typing.
**Contract invariant**: Config completeness and key-level types are compile/runtime verifiable.
**Allowed variation**: Non-literal string fields (e.g., model name) can vary.
**Assertion scope rationale**: Minimal schema-level checks, no behavioral semantics.
**Fragility check**: No dependence on exact dict formatting/alignment.

#### T-19: `DEFAULT_CONFIG` constants match Section 1 defaults and are override-spreadable

**Contract**: Default constant values are as specified and support `{**DEFAULT_CONFIG, ...}` test override pattern.
**Setup**: direct value assertions for the canonical defaults and both static/runtime checks on override dict.
**Expected**: Values match (`sample_rate=16000`, `audio_channels=1`, `audio_format="float32"`, `whisper_device="cuda"`); override dict satisfies `KoeConfig`.
**Discriminating power**: Catches silent default drift and non-spreadable structure regressions.
**Contract invariant**: Single source of truth defaults remain stable and typed.
**Allowed variation**: Additional future config keys only if design contract is updated.
**Assertion scope rationale**: Validate only semantically critical defaults listed by design/spec.
**Fragility check**: No assertion on field ordering in dict literal.

### `main.py` invocation contracts

#### T-20: `main()` always exits and maps unexpected exceptions to exit code 2

**Contract**: `main()` never leaks exceptions and unconditionally exits.
**Setup**: patch `run_pipeline` to raise `Exception("boom")`; patch `sys.exit` spy.
**Expected**: no exception escapes `main()`; `sys.exit(2)` is invoked exactly once.
**Discriminating power**: Catches top-level exception leakage and wrong exit classification.
**Contract invariant**: CLI boundary is fail-closed and explicit.
**Allowed variation**: Notification best-effort internals are not asserted.
**Assertion scope rationale**: Exit code and no-raise are the minimal observable contract.
**Fragility check**: Does not assert log strings or notification transport.

#### T-21: `run_pipeline(config)` returns only `PipelineOutcome` and preserves cleanup-on-failure contract

**Contract**: Signature is `(KoeConfig) -> PipelineOutcome` and documented cleanup semantics are preserved as invocation-level obligations.
**Setup**: static type test for parameter/return contract; behavioral test placeholder marked `xfail` until stage functions exist, asserting cleanup hooks called on injected mid-pipeline failure.
**Expected**: type contract passes now; cleanup behavioral proof activates when sections 2-6 land.
**Discriminating power**: Prevents signature drift now and protects against future missing-finally cleanup bug.
**Contract invariant**: Output vocabulary and cleanup guarantee are part of public contract.
**Allowed variation**: Internal pipeline ordering implementation details remain out of Section 1 scope.
**Assertion scope rationale**: Split immediate (type-level) vs deferred (runtime) obligations keeps this section bounded.
**Fragility check**: Avoids asserting stage internals before those modules exist.

#### T-22: `outcome_to_exit_code` implements pure, total mapping contract including all error paths

**Contract**: All eight `PipelineOutcome` literals map exactly as specified to `ExitCode`.
**Setup**: parametrized unit test over full mapping table.
**Expected**: `success -> 0`; six controlled failures + `no_focus/no_speech -> 1`; `error_unexpected -> 2`.
**Discriminating power**: Catches missing case handling, incorrect mapping, or non-total function.
**Contract invariant**: Exit semantics are deterministic and I/O-free.
**Allowed variation**: Implementation can use `match` or dict lookup.
**Assertion scope rationale**: Full table-driven check is the smallest totality proof.
**Fragility check**: No assertions on logging side effects.

## Requirement Traceability

| Requirement | Source | Proved By Contract | Proved By Tests |
|-------------|--------|--------------------|-----------------|
| AC-1: Section 1 module surface under `src/koe/` exists | `spec.md:33` | `types.py`, `config.py`, `main.py` importable contracts | T-20, T-21, T-22 (plus file-presence checks in implementation gate) |
| AC-2: Shared pipeline types defined in one place with explicit contracts | `spec.md:34` | all `types.py` contracts | T-01 through T-17 |
| AC-3 (partial): typed config defaults and runnable CLI entrypoint contract | `spec.md:35` | `KoeConfig`, `DEFAULT_CONFIG`, `main()` | T-18, T-19, T-20 |
| AC-5: type/lint baseline runnable and clean | `spec.md:37` | static literal/newtype/result narrowing and strict annotations | T-01, T-04, T-05, T-13, T-15, T-16, T-17, T-18, T-21 + lint/typecheck gates |

## What Is NOT Tested (and Why)

- Actual hotkey listener, X11 focus checks, audio capture, transcription runtime, insertion, and notifications: out of Section 1 API surface; these belong to Sections 2-6.
- Tool installation and OS dependency availability (`xdotool`, `xclip`, CUDA runtime): integration/environment contracts, not Section 1 type/config/invocation contract proofs.
- Full cleanup execution path internals inside `run_pipeline`: deferred runtime verification until stage modules exist; Section 1 proves contract shape and mandatory future obligation.

## Test Execution Order

1. Foundation static checks (`T-01`, `T-04`, `T-05`, `T-13`, `T-15`, `T-16`, `T-17`, `T-18`, `T-21` static portion) via `uv run pyright`.
2. Runtime type-shape checks for typed dict and union contracts (`T-02`, `T-03`, `T-06` to `T-12`, `T-14`, `T-18`, `T-19`) via `pytest` + `typeguard`.
3. Pure invocation mapping and CLI error-path checks (`T-20`, `T-22`) via `pytest`.
4. Deferred cleanup-behavior proof in `T-21` once Sections 2-6 exist; remove `xfail` then.

If phase 1 fails, phases 2-4 results are not trusted.

## Design Gaps

- No blocking design gaps found for Section 1 API-surface testability.
- Deferred obligation (non-blocking): `run_pipeline` cleanup behavior in `T-21` requires downstream stage modules from Sections 2-6 to execute meaningful runtime assertions.

Test specification complete.

**Location**: `thoughts/projects/2026-02-20-koe-m1/working/section-1-test-spec.md`
**Summary**: 22 tests across 27 API contracts
**Design gaps**: none blocking (1 deferred cross-section runtime obligation)

Ready for planner.
