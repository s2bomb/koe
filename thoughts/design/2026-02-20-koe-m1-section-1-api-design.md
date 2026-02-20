# Koe M1 Section 1 API Design: Foundations and Delivery Baseline

---
date: 2026-02-20
author: opencode (design-clone)
status: approved-for-implementation
project: koe-m1
section: "Section 1: Foundations and Delivery Baseline"
source_spec: thoughts/projects/2026-02-20-koe-m1/spec.md
source_research: thoughts/projects/2026-02-20-koe-m1/working/section-1-research.md
scope: "types.py, config.py, main.py invocation contracts only"
---

## The Core Principle

**Define a compile-time-verified shared type vocabulary, immutable runtime defaults, and a slim invocation contract so every later section implements against a single consistent interface that the Pyright compiler enforces.**

Section 1 has no runtime behaviour to deliver. Its job is to make runtime behaviour in Sections 2–7 impossible to mis-type. Every type defined here becomes a compiler-enforced invariant at every module boundary. Every constant in `DEFAULT_CONFIG` is the single source of truth that later sections override only in tests. `main.py`'s signatures define the seam between CLI invocation and pipeline logic — the only point future sections need to satisfy to be composable.

---

## Module-to-Acceptance-Criteria Mapping

| Module | Section 1 Acceptance Criterion |
|--------|--------------------------------|
| `types.py` | AC-2: Shared pipeline types defined in one place with explicit contracts for hotkey action, window focus result, audio artefact path, transcription result, clipboard state, and notification kind (`spec.md:34`) |
| `config.py` | AC-3 (partial): `pyproject.toml` constrained M1 runtime libraries; this module surfaces those as typed constants and a spreadable `KoeConfig` structure (`spec.md:35`) |
| `main.py` | AC-3 (partial): Declares the runnable CLI entrypoint wired to `[project.scripts]`; AC-5: Is fully type/lint clean under current toolchain policy (`spec.md:35`, `spec.md:37`) |
| All three | AC-1: File presence under `src/koe/` (`spec.md:33`); AC-5: `uv run pyright` and `uv run ruff check` pass on all three module stubs (`spec.md:37`) |
| `pyproject.toml` (infrastructure) | AC-3: Declares `faster-whisper`, `sounddevice`, `numpy`, `pynput`, `pytest`, `typeguard`, and `[project.scripts]` entrypoint (`spec.md:35`) |
| `Makefile` (infrastructure) | AC-4: Provides `lint`, `typecheck`, `test`, `run` as documented commands (`spec.md:36`) |

---

## Types: `src/koe/types.py`

All shared pipeline types. **Zero logic. Zero imports from other `koe` modules.**

```python
"""Shared pipeline type vocabulary for Koe M1.

All types that cross module boundaries are defined here.
No logic. No imports from other koe modules.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, NewType, TypedDict


# ── Domain opaque aliases ──────────────────────────────────────────────────────

AudioArtifactPath = NewType("AudioArtifactPath", Path)
"""Path to a temporary WAV file produced by the audio capture stage.

Using NewType prevents accidental substitution of an arbitrary Path where
a capture-produced artefact is required. Assignment from bare Path is a
Pyright type error.
"""

WindowId = NewType("WindowId", int)
"""X11 window identifier returned by `xdotool getactivewindow`.

Using NewType prevents accidental use of arbitrary integers as window IDs.
"""


# ── Result type ────────────────────────────────────────────────────────────────

class Ok[T](TypedDict):
    """Successful outcome carrying a typed value.

    Narrow with: if result["ok"]: use result["value"]
    """
    ok: Literal[True]
    value: T


class Err[E](TypedDict):
    """Failed outcome carrying a typed error.

    Narrow with: if not result["ok"]: use result["error"]
    """
    ok: Literal[False]
    error: E


type Result[T, E] = Ok[T] | Err[E]
"""Discriminated union for expected failures.

Callers are forced by Pyright to handle both arms. Use `result["ok"]` as
the narrowing key. Truly exceptional situations (programmer bugs, corrupted
state) throw exceptions instead of using this type.

Example narrowing:
    match result["ok"]:
        case True:  text = result["value"]
        case False: error = result["error"]
"""


# ── Hotkey types ───────────────────────────────────────────────────────────────

type HotkeyAction = Literal["start"] | Literal["stop"]
"""Toggle event emitted by the hotkey listener (hotkey.py, Section 2).

- "start": first invocation — begin recording
- "stop":  second invocation — end recording and proceed to transcription

For M1 the listener runs in a separate thread; this type is the sole data
token it produces. The pipeline consumes it as a signal, not as a value.
"""


# ── Window focus types ─────────────────────────────────────────────────────────

class FocusedWindow(TypedDict):
    """X11 focused window state at the moment of invocation.

    Produced by window.py (Section 2). Consumed by main.py and insert.py.
    """
    window_id: WindowId
    title: str


type WindowFocusResult = FocusedWindow | None
"""Result of querying X11 for the currently focused window.

None means no window was focused; the pipeline must show a notification and
exit before audio capture begins.

Note: this is the DATA type flowing between pipeline stages. The function
`check_focused_window()` wraps it in Result[FocusedWindow, FocusError] to
carry the error reason when xdotool itself fails (vs. simply no focus).
"""


# ── Audio types ────────────────────────────────────────────────────────────────

# The audio artefact path type is AudioArtifactPath (defined above as NewType).
# audio.py (Section 3) produces AudioArtifactPath; transcribe.py (Section 4)
# consumes it; main.py cleanup deletes it.


# ── Transcription types ────────────────────────────────────────────────────────

class TranscriptionText(TypedDict):
    """Successful transcription yielding usable text.

    `text` is non-empty and non-whitespace. The insert stage can consume it directly.
    """
    kind: Literal["text"]
    text: str


class TranscriptionNoSpeech(TypedDict):
    """Audio contained no usable speech (empty or whitespace-only output).

    The pipeline must emit a "no speech detected" notification and exit
    cleanly without attempting insertion.
    """
    kind: Literal["empty"]


class TranscriptionFailure(TypedDict):
    """Transcription could not complete.

    Covers: CUDA unavailable, model not loaded, CTranslate2 runtime error.
    The pipeline must emit an error notification and exit cleanly.
    """
    kind: Literal["error"]
    error: TranscriptionError


type TranscriptionResult = TranscriptionText | TranscriptionNoSpeech | TranscriptionFailure
"""Three-armed union for Whisper inference outcomes.

NOT wrapped in Result[T, E] because there are three distinct arms, not two.
Callers narrow on result["kind"]:

    match result["kind"]:
        case "text":  text = result["text"]
        case "empty": ...notify no speech
        case "error": ...notify error
"""


# ── Clipboard types ────────────────────────────────────────────────────────────

class ClipboardState(TypedDict):
    """Snapshot of clipboard content saved before Koe writes to it.

    Used by insert.py (Section 5) to restore the original clipboard after paste.
    `content` is None when the clipboard was empty or held non-text data at
    the time of capture. Restoration of None means clearing the clipboard.
    """
    content: str | None


# ── Notification types ─────────────────────────────────────────────────────────

type NotificationKind = Literal[
    "recording_started",    # audio capture has begun; user can speak
    "processing",           # Whisper inference is running
    "completed",            # transcription inserted; clipboard restored
    "error_focus",          # no focused window; run aborted before capture
    "error_audio",          # microphone unavailable or capture failed
    "error_transcription",  # CUDA unavailable or Whisper inference failed
    "error_insertion",      # xclip/xdotool unavailable or paste failed
    "error_dependency",     # required system tool missing at startup preflight
]
"""All valid notification states for the M1 pipeline.

Maps directly to the user-visible phase model from spec.md Section 6.
notify.py (Section 6) accepts exactly this type — no other strings are valid.
"""


# ── Error types ────────────────────────────────────────────────────────────────

class FocusError(TypedDict):
    """No focused window was found; run cannot proceed to recording."""
    category: Literal["focus"]
    message: str


class AudioError(TypedDict):
    """Microphone unavailable or audio capture failed."""
    category: Literal["audio"]
    message: str
    device: str | None
    """Device name or index if known; None if the error preceded device selection."""


class TranscriptionError(TypedDict):
    """Whisper inference failed: CUDA unavailable, model load error, or runtime fault."""
    category: Literal["transcription"]
    message: str
    cuda_available: bool
    """False when CUDA was not available — the primary expected failure mode for M1."""


class InsertionError(TypedDict):
    """Text could not be inserted via clipboard and xdotool.

    `transcript_text` is preserved so the user can manually paste the result.
    The pipeline must surface this in the error notification.
    """
    category: Literal["insertion"]
    message: str
    transcript_text: str


class DependencyError(TypedDict):
    """A required system binary or library is missing or inaccessible."""
    category: Literal["dependency"]
    message: str
    missing_tool: str
    """Name of the missing tool, e.g. "xdotool", "xclip", "notify-send"."""


type KoeError = (
    FocusError
    | AudioError
    | TranscriptionError
    | InsertionError
    | DependencyError
)
"""Discriminated union of all expected pipeline errors.

Narrow by `error["category"]` to determine which subtype to access.
Each arm maps to exactly one NotificationKind for user feedback.
"""


# ── Pipeline outcome types ─────────────────────────────────────────────────────

type PipelineOutcome = Literal[
    "success",               # text inserted; clipboard restored; artefact removed
    "no_focus",              # no window focused; user notified; clean exit
    "no_speech",             # empty transcription; user notified; clean exit
    "error_dependency",      # preflight failed; user notified; clean exit
    "error_audio",           # audio capture failed; user notified; clean exit
    "error_transcription",   # Whisper failed; user notified; clean exit
    "error_insertion",       # paste failed; user notified; clean exit
    "error_unexpected",      # unhandled exception; exit attempted with code 2
]
"""All possible outcomes of a single Koe invocation.

Returned by `run_pipeline()` in main.py. Enables integration tests to assert
outcomes without inspecting exit codes or stdout.
"""


type ExitCode = Literal[0, 1, 2]
"""Process exit code contract.

- 0: success (transcription inserted, pipeline ran to completion)
- 1: controlled failure (user was notified; clean exit on expected error path)
- 2: unexpected / unhandled exception (clean exit was attempted)

Using Literal prevents passing arbitrary integers to sys.exit.
"""
```

> **Implementation note — generic TypedDict syntax**: `class Ok[T](TypedDict)` uses PEP 695 generic class syntax (Python 3.12+, required by `pyproject.toml:9`). Verify Pyright 1.1.408+ compatibility during implementation. Fallback if unsupported: `class Ok(TypedDict, Generic[T_co]):` with an explicit covariant `TypeVar`.

---

## Config: `src/koe/config.py`

Immutable runtime constants. **Zero logic. Zero imports from other `koe` modules.**

```python
"""Koe M1 runtime configuration constants.

All M1 defaults live here. No validation logic — this is a compile-time
contract verified by Pyright. Configuration is intentionally pure data.

Usage:
    from koe.config import DEFAULT_CONFIG, KoeConfig

Test overrides (spread syntax):
    test_config: KoeConfig = {**DEFAULT_CONFIG, "whisper_model": "tiny.en"}
"""
from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, TypedDict


class KoeConfig(TypedDict, total=True):
    """Complete M1 runtime configuration.

    All fields are required (total=True). A missing field is a type error,
    not a runtime KeyError. Pass DEFAULT_CONFIG as the production value;
    spread-and-override for test variants.
    """

    # ── Hotkey ──────────────────────────────────────────────────────────────
    hotkey_combo: str
    """pynput key-combination string. Example: '<super>+<shift>+v'.
    Configurable to avoid conflicts with window manager bindings.
    """

    # ── Audio capture ────────────────────────────────────────────────────────
    sample_rate: int
    """Sample rate in Hz. Whisper requires 16 000; do not change for M1."""

    audio_channels: int
    """Channel count. Mono (1) is correct for speech transcription."""

    audio_format: Literal["float32"]
    """WAV sample format. Literal["float32"] because Whisper requires float32.
    Widening this type to str in a future milestone requires an explicit
    migration at this field's definition.
    """

    # ── Whisper inference ────────────────────────────────────────────────────
    whisper_model: str
    """Faster-Whisper model identifier. Default "base.en" balances speed and
    accuracy on RTX 3080 Ti; upgradeable to "small.en" or "medium.en".
    """

    whisper_device: Literal["cuda"]
    """Inference device. Literal["cuda"] makes CPU fallback a Pyright type
    error for M1. Future milestone: widen to Literal["cuda", "cpu"].
    """

    whisper_compute_type: str
    """CTranslate2 compute type. "float16" maximises throughput on RTX 3080 Ti."""

    # ── Text insertion ───────────────────────────────────────────────────────
    paste_key_modifier: str
    """Primary modifier key for paste keystroke. Default "ctrl".
    Terminals that require Ctrl+Shift+V can override to "ctrl+shift".
    See spec.md open question on paste keystroke configurability.
    """

    paste_key: str
    """Key for paste keystroke. Combined with paste_key_modifier at insertion time."""

    # ── Concurrency guard ────────────────────────────────────────────────────
    lock_file_path: Path
    """Filesystem path used for single-instance guard (Section 2).
    Must be on a filesystem that supports exclusive file creation.
    """

    # ── Temporary file management ────────────────────────────────────────────
    temp_dir: Path
    """Directory for temporary WAV artefacts. Artefacts are removed on all
    exit paths (success and error). Must be writable by the running user.
    """


DEFAULT_CONFIG: Final[KoeConfig] = {
    "hotkey_combo":       "<super>+<shift>+v",
    "sample_rate":        16_000,
    "audio_channels":     1,
    "audio_format":       "float32",
    "whisper_model":      "base.en",
    "whisper_device":     "cuda",
    "whisper_compute_type": "float16",
    "paste_key_modifier": "ctrl",
    "paste_key":          "v",
    "lock_file_path":     Path("/tmp/koe.lock"),
    "temp_dir":           Path("/tmp"),
}
"""Production M1 defaults. Every value is grounded in the project brief
(sources/project-brief.md section 11) and the M1 decision register
(thoughts/specs/2026-02-20-koe-m1-spec.md).

Do NOT mutate. Test overrides: {**DEFAULT_CONFIG, "key": new_value}.
"""
```

---

## Main: `src/koe/main.py` Invocation Contracts

Entry-point and pipeline runner signatures. **No business logic. No direct OS calls.**

```python
"""Koe M1 entry point.

Orchestrates the linear pipeline procedurally. No business logic here.
Each pipeline stage is delegated to its owning module (Sections 2–6).

CLI entrypoint declared in pyproject.toml:
    [project.scripts]
    koe = "koe.main:main"
"""
from __future__ import annotations

from koe.config import DEFAULT_CONFIG, KoeConfig
from koe.types import ExitCode, PipelineOutcome


def main() -> None:
    """CLI entry point. Load DEFAULT_CONFIG, run pipeline, exit with code.

    Guarantees:
    - Never raises — all exceptions are caught and mapped to ExitCode 2.
    - Always calls sys.exit; does not return normally.
    - Attempts cleanup (artefact removal, clipboard restore) on all paths,
      including unexpected exceptions.
    """
    ...


def run_pipeline(config: KoeConfig) -> PipelineOutcome:
    """Execute the full M1 pipeline under the given config.

    Returns a PipelineOutcome for testability without I/O assertions.
    Guarantees cleanup (artefact removal, clipboard restore) on all exit paths,
    including midway failures — cleanup always runs in the equivalent of a
    `finally` block.

    Pipeline stages (typed placeholders; implemented in Sections 2–6):

        Stage 1 — dependency_preflight(config)
            Signature: (config: KoeConfig) -> Result[None, DependencyError]
            Owner: Section 2
            Checks: xdotool, xclip, notify-send availability; CUDA presence
            On Err: emit error_dependency notification → return "error_dependency"

        Stage 2 — guard_single_instance(config)
            Signature: (config: KoeConfig) -> Result[None, KoeError]
            Owner: Section 2
            Checks: lock file; if locked, another run is active
            On Err: emit "already running" notification → return "error_unexpected"

        Stage 3 — check_focused_window(config)
            Signature: (config: KoeConfig) -> Result[FocusedWindow, FocusError]
            Owner: Section 2
            Checks: xdotool getactivewindow; None = no focused window
            On Err: emit error_focus notification → return "no_focus"

        Stage 4 — run_audio_capture(config)
            Signature: (config: KoeConfig) -> Result[AudioArtifactPath, AudioError]
            Owner: Section 3
            Side effect: writes temp WAV to config["temp_dir"]
            On Err: emit error_audio notification → return "error_audio"

        Stage 5 — transcribe_audio(artifact, config)
            Signature: (artifact: AudioArtifactPath, config: KoeConfig) -> TranscriptionResult
            Owner: Section 4
            On "empty": emit processing→no_speech notification → return "no_speech"
            On "error": emit error_transcription notification → return "error_transcription"

        Stage 6 — insert_text(text, window, config)
            Signature: (text: str, window: FocusedWindow, config: KoeConfig)
                        -> Result[None, InsertionError]
            Owner: Section 5
            On Err: emit error_insertion notification (with transcript_text) →
                    return "error_insertion"

        Cleanup (always runs, regardless of which stage failed):
            cleanup_artifact(artifact | None, config) -> None
            restore_clipboard(state | None, config)   -> None

    Args:
        config: Full M1 runtime configuration. Pass DEFAULT_CONFIG for
                production; override specific keys in tests.

    Returns:
        PipelineOutcome literal describing how the pipeline ended.
        Map to ExitCode via outcome_to_exit_code() for sys.exit.
    """
    ...


def outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode:
    """Pure mapping from PipelineOutcome to process exit code.

    No I/O. Testable in isolation.

    Mapping:
        "success"             -> 0
        "no_focus"            -> 1  (controlled; user was notified)
        "no_speech"           -> 1  (controlled; user was notified)
        "error_dependency"    -> 1  (controlled; user was notified)
        "error_audio"         -> 1  (controlled; user was notified)
        "error_transcription" -> 1  (controlled; user was notified)
        "error_insertion"     -> 1  (controlled; user was notified)
        "error_unexpected"    -> 2  (unhandled; clean exit was attempted)

    Args:
        outcome: PipelineOutcome from run_pipeline().

    Returns:
        ExitCode for sys.exit(). Literal[0, 1, 2] only — not an arbitrary int.
    """
    ...
```

---

## Error Handling Strategy

### Returns `Result[T, E]` — expected failures

Each pipeline stage that encounters an **anticipated failure condition** returns
`Result[T, E]`. The caller cannot silently ignore the error arm; Pyright enforces handling.

| Stage function (Section) | Return type | Rationale |
|--------------------------|-------------|-----------|
| `dependency_preflight()` (S2) | `Result[None, DependencyError]` | Missing system tools are expected in a fresh environment |
| `guard_single_instance()` (S2) | `Result[None, KoeError]` | Concurrent invocation is a recoverable user condition |
| `check_focused_window()` (S2) | `Result[FocusedWindow, FocusError]` | No focus is a valid user state, not a bug |
| `run_audio_capture()` (S3) | `Result[AudioArtifactPath, AudioError]` | No microphone or permission denied are common environment states |
| `insert_text()` (S5) | `Result[None, InsertionError]` | xdotool/xclip failures are environment-specific, predictable |

### Returns `TranscriptionResult` directly — three-armed, not two-armed

`transcribe_audio()` returns `TranscriptionResult` (not `Result[T, E]`) because it has
three distinct outcomes (`text | empty | error`). A two-armed Result would collapse
"no speech" and "error" into the same Err arm, losing semantic clarity.

### Raises exception — programmer bugs only

| Scenario | Why exception |
|----------|---------------|
| `cleanup_artifact()` called with wrong type | Type system prevents this; occurrence is a developer bug |
| Module import-time failures (e.g. missing `koe.types`) | Fatal configuration error; the process cannot proceed |

### `main()` top-level catch

`main()` wraps `run_pipeline()` in a `try/except Exception` that:
1. Attempts to emit an `"error_unexpected"` notification via `notify.py` (best-effort)
2. Attempts artefact and clipboard cleanup with any state captured before the exception
3. Calls `sys.exit(2)` unconditionally

Notification emission failures must **not** mask or re-raise the original exception
(see `spec.md` Section 6, notification emission failure criterion).

---

## Observability Design

Python stdlib `logging` is the observability mechanism — no external dependency.
All log entries use the `koe` logger namespace.

| Location | Level | Message / key attributes |
|----------|-------|--------------------------|
| `run_pipeline` entry | `INFO` | `"pipeline started config_model=%s"` with whisper_model |
| `run_pipeline` exit | `INFO` | `"pipeline outcome=%s"` with PipelineOutcome value |
| `run_pipeline` unexpected exception | `ERROR` | `"pipeline unexpected exception"` + full traceback via `exc_info=True` |
| `outcome_to_exit_code` | — | No logging; pure function |
| `config.py` | — | No logging; constants only |
| `types.py` | — | No logging; types only |

**What matters at 2am:**
- The `PipelineOutcome` literal in the `INFO` log distinguishes `"no_focus"` from
  `"error_audio"` from `"success"` without reading notification state
- `InsertionError.transcript_text` must be logged at `WARNING` level so dictated
  text is never silently lost on a paste failure
- `TranscriptionError.cuda_available: False` distinguishes "GPU missing" from
  "model file missing" — both need different remediation

---

## Test Strategy

### Toolchain gate (Section 1 completion criteria)

- [ ] `uv run pyright` → `0 errors, 0 warnings, 0 informations` on all three module stubs
- [ ] `uv run ruff check src/` → `All checks passed!`
- [ ] `uv run pytest tests/` → all pass (stubs import cleanly; no unimplemented runtime deps are imported)

### `tests/test_types.py` — shape and invariant tests

**Pyright-level (static, no runtime assertions needed):**
- `AudioArtifactPath` is not assignable from bare `Path` (Pyright type error if broken)
- `Ok[str]` and `Err[KoeError]` narrow correctly on `result["ok"]` (Pyright narrowing test)
- `whisper_device: Literal["cuda"]` on `KoeConfig` rejects `"cpu"` at assignment (Pyright)

**Runtime / `typeguard` assertions:**
- [ ] `check_type({"ok": True, "value": "hello"}, Ok[str])` passes
- [ ] `check_type({"ok": False, "error": {...}}, Err[FocusError])` passes
- [ ] `check_type({"window_id": 1, "title": "terminal"}, FocusedWindow)` passes
- [ ] `check_type({"kind": "text", "text": "hello"}, TranscriptionText)` passes
- [ ] `check_type({"kind": "empty"}, TranscriptionNoSpeech)` passes
- [ ] `check_type({"content": None}, ClipboardState)` passes
- [ ] `KoeError` category field is one of the five expected `Literal` values

### `tests/test_config.py` — constant correctness

- [ ] `check_type(DEFAULT_CONFIG, KoeConfig)` passes (typeguard runtime shape check)
- [ ] `DEFAULT_CONFIG["sample_rate"] == 16_000`
- [ ] `DEFAULT_CONFIG["audio_format"] == "float32"`
- [ ] `DEFAULT_CONFIG["whisper_device"] == "cuda"`
- [ ] `DEFAULT_CONFIG["audio_channels"] == 1`
- [ ] Spread-and-override is Pyright-clean: `{**DEFAULT_CONFIG, "whisper_model": "tiny.en"}` satisfies `KoeConfig`
- [ ] `check_type({**DEFAULT_CONFIG, "whisper_model": "tiny.en"}, KoeConfig)` passes

### `tests/test_main.py` — invocation contract tests

- [ ] `outcome_to_exit_code("success") == 0`
- [ ] `outcome_to_exit_code("no_focus") == 1`
- [ ] `outcome_to_exit_code("no_speech") == 1`
- [ ] `outcome_to_exit_code("error_unexpected") == 2`
- [ ] All eight `PipelineOutcome` literals map to a valid `ExitCode` (parametrize)
- [ ] `from koe.main import main, run_pipeline, outcome_to_exit_code` imports without side effects
- [ ] `run_pipeline` accepts `KoeConfig`-typed argument (Pyright static check)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Type checker | Pyright strict only | Existing `pyproject.toml:24` policy; no additional tooling required; mypy vs Pyright resolved in `thoughts/specs/2026-02-20-koe-m1-spec.md:60` |
| Config structure | `KoeConfig` TypedDict + `DEFAULT_CONFIG: Final` | Spreadable for test overrides; Pyright enforces shape at assignment; no runtime overhead |
| Pydantic in Section 1 | **Not used** | Config is compile-time constants, not user-provided input; `pydantic` runtime overhead is unjustified here; aligns with "minimal dependencies" brief directive; open question `spec.md:144` is deferred — if external config files are added in future milestones, pydantic re-evaluation is appropriate then |
| Result type representation | TypedDict discriminated union `Ok[T] \| Err[E]` | Pyright narrows on `result["ok"]`; callers cannot silently ignore the error arm; consistent with "loud compiler" CEO directive (`project-brief.md:16`) |
| TranscriptionResult shape | Three-armed union (text / empty / error), not `Result[T, E]` | "No speech" and "error" are distinct user experiences requiring different notifications; collapsing them into one `Err` arm loses semantic precision |
| `ExitCode` type | `Literal[0, 1, 2]` | Prevents passing arbitrary integers to `sys.exit`; documents the full code vocabulary at the type level |
| `PipelineOutcome` type | `Literal[...]` union of named states | `run_pipeline` is independently testable without I/O; outcome literals are more readable than exit codes in assertions |
| `whisper_device` field type | `Literal["cuda"]` (not `str`) | Makes CPU fallback a Pyright type error for M1; M2/M3 can widen to `Literal["cuda", "cpu"]` as an explicit breaking change |
| `WindowFocusResult` | `FocusedWindow \| None` (not a third TypedDict arm) | Binary state: either a window is focused or it is not; xdotool failure itself is `DependencyError`, handled at preflight before this check runs |
| Generic TypedDict syntax | PEP 695 `class Ok[T](TypedDict)` | Python 3.12+ (matches `requires-python = ">=3.12"`). **Verify with Pyright 1.1.408 during implementation.** Fallback: `class Ok(TypedDict, Generic[T_co])` with explicit covariant TypeVar |
| `KoeConfig` total=True | All fields required | A partially-configured Koe is a bug, not a valid state; missing fields should be caught at construction, not at the callsite that first reads the field |

---

## Infrastructure Requirements

*Not API contracts — included for Section 1 acceptance completeness.*

### `pyproject.toml` required additions

```toml
# CLI entrypoint (AC-3)
[project.scripts]
koe = "koe.main:main"

# Runtime dependencies (add to [project] dependencies — AC-3)
# "faster-whisper>=1.0.0"
# "sounddevice>=0.4.6"
# "numpy>=1.26.0"
# "pynput>=1.7.6"
# Note: pydantic is currently present but unused by Section 1 modules.
# See Design Decisions above for context on deferred removal.

# Test/dev dependencies (add to [dependency-groups].dev — AC-3)
# "pytest>=8.0.0"
# "typeguard>=4.3.0"
```

### `Makefile` (AC-4)

```makefile
.PHONY: lint typecheck test run

lint:
	uv run ruff check .

typecheck:
	uv run pyright

test:
	uv run pytest

run:
	uv run koe
```

---

## Integration Notes

**How `types.py` is consumed across sections:**

| Section | Imports from `types.py` |
|---------|-------------------------|
| Section 2 (hotkey, window) | `HotkeyAction`, `FocusedWindow`, `WindowFocusResult`, `FocusError`, `DependencyError`, `Result` |
| Section 3 (audio) | `AudioArtifactPath`, `AudioError`, `Result` |
| Section 4 (transcribe) | `TranscriptionResult`, `TranscriptionText`, `TranscriptionNoSpeech`, `TranscriptionFailure`, `TranscriptionError` |
| Section 5 (insert) | `ClipboardState`, `InsertionError`, `Result` |
| Section 6 (notify) | `NotificationKind`, `KoeError` |
| Section 7 (tests) | All types — for runtime `typeguard` assertions |

**How `config.py` is consumed:**
- `DEFAULT_CONFIG` is the only production-time value; passed explicitly to every stage function
- Tests pass `{**DEFAULT_CONFIG, "key": override_value}` — no monkey-patching of module globals
- This pattern keeps every stage function testable in isolation without import-level side effects

**How `main.py` is consumed:**
- `main()` is the sole symbol exposed to the OS via `[project.scripts]`
- `run_pipeline(config)` is the testable seam — all integration tests call this directly
- `outcome_to_exit_code(outcome)` is a pure function with no I/O — trivially unit-testable and independently verifiable

**Open questions carried forward (non-blocking for Section 1):**
- Pydantic removal: not required in Section 1; deferred to implementation planning
- Paste keystroke configurability (`paste_key_modifier` + `paste_key` fields in `KoeConfig` are already designed to accommodate `Ctrl+Shift+V`)
- Binary/non-text clipboard restoration: `ClipboardState.content: str | None` — `None` covers the non-text case; M1 limitation should be documented in README
