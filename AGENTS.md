# koe

Global hotkey speech-to-text for Linux. Local Whisper inference on GPU, pipes transcriptions into any focused input.

> See `thoughts/` for the project spec, API designs, and implementation plans.

---

## Foundation

This codebase is built on observable facts, not preferences. Every principle and rule below traces back to one or more of these truths. If a rule conflicts with a truth, the rule is wrong.

- **The process model is the ground truth.** Koe is single-shot: invoke, record, transcribe, insert, exit. No daemon. No persistent state. No background threads beyond what libraries require internally. This shapes every decision -- cleanup is guaranteed by process exit, concurrency is guarded by a lockfile, state does not survive invocations. Architecture that assumes persistence is wrong architecture.
- **Iteration count determines quality.** The developer who tests 500 hotkey-to-paste cycles finds edge cases the developer who tests 50 does not. Every second of build time, test time, and manual reproduction time is a tax on every iteration.
- **Bugs are states outside the specification.** Every invalid state your type system can represent is a bug waiting to happen. Fewer representable states = fewer possible bugs. This is combinatorics, not philosophy.
- **A function you can read top-to-bottom is the only unit a human can fully reason about.** Hidden state is hidden bugs. The signature must tell the truth: what goes in, what comes out, what side effects occur.
- **The type checker proves types. Tests prove values.** Pyright strict enforces types, discriminated unions, literal constraints, and exhaustive narrowing. Code that type-checks has already passed a verification gauntlet no test can improve upon. Tests exist to prove what the type checker cannot see: that computations are correct, that modules compose, that runtime behaviour is right.
- **Complexity compounds. Simplicity scales.** Every abstraction is a bet that its cost will be repaid. The burden of proof is on complexity, not simplicity.

### When Rules Conflict

This document contains truths (observable facts, proven observations), principles (engineering beliefs), and rules (concrete practices with scope). When they conflict:

1. **Iterate.** Every decision serves iteration speed. When in doubt, pick the choice that gets you to "see the result" fastest.
2. **Prevent.** Make invalid states impossible. Validate at the gate. Assert invariants. Crash on violations.
3. **Simplify.** Use the simplest structure that fits the requirements. Flat module until proven insufficient. Direct subprocess call until proven slow.
4. **Listen.** When the code resists, the structure is wrong. Pain is signal. Stop and reorganise.

These four are ordered by priority. A developer should sacrifice simplicity (3) before sacrificing prevention (2), and sacrifice prevention before sacrificing iteration speed (1). Rules apply within their stated scope -- outside that scope, fall back to these principles.

---

## Platform

**Linux / X11 / CUDA.** Koe M1 targets Arch Linux under X11 with NVIDIA CUDA for local Whisper inference. The runtime requires Python 3.12+, `xdotool`, `xclip`, and `notify-send` as system dependencies.

Wayland, macOS, and CPU-only inference are out of scope for M1. `whisper_device` is typed as `Literal["cuda"]` -- CPU fallback is a type error, not a runtime decision.

---

## Iteration Speed

Iteration time is not test time. It is the full cycle from code change to seeing the result in the exact scenario you care about. For a speech-to-text tool, this means: change code, run the type checker, run the test suite, invoke the hotkey, speak, and verify the pasted output. Every second of that loop matters.

`make lint`, `make typecheck`, `make test`, `make run` -- these must stay fast and correct. If a check becomes slow enough to skip, it will be skipped, and the bugs it would have caught will ship.

> Evans: "Iteration count is the only number that matters in game development. I have tried this 500 times and I finally found the golden thing. And if it takes you 20 minutes every time, you will never make it to the 500th golden thing."

The quote is about game development. The truth is universal.

---

## Where Code Lives

> **IMPORTANT**: Every file must have a clear home. Koe is a single flat package -- there is no decision tree to walk. If a module does not own exactly one pipeline concern, it is wrong.

### Project Layout

```
src/koe/          — application source (single flat package)
tests/            — pytest test suite
thoughts/         — specs, designs, plans, project working files
  design/         — API design documents
  plans/          — implementation plans
  specs/          — requirements specifications
  projects/       — project working directories
docs/             — user-facing documentation
```

### Module Map

Every module in `src/koe/` owns exactly one pipeline concern. The module list is small and explicit:

| Module         | Concern                                                          |
| -------------- | ---------------------------------------------------------------- |
| `types.py`     | Shared type vocabulary. Zero logic. Zero internal imports.       |
| `config.py`    | Immutable runtime constants. Zero logic. Imports only `types`.   |
| `main.py`      | Pipeline orchestration. Composes all modules. CLI entry point.   |
| `hotkey.py`    | Invocation guard and instance locking.                           |
| `window.py`    | X11 context validation and focused-window lookup.                |
| `audio.py`     | Microphone capture and temp WAV artefact lifecycle.              |
| `transcribe.py`| Whisper GPU inference on audio artefacts.                        |
| `insert.py`    | Clipboard-safe text insertion via X11 tooling.                   |
| `notify.py`    | Desktop notification emission (best-effort, non-raising).        |

### Dependencies Flow One Direction

```
types.py <- config.py <- all other modules
                          main.py orchestrates all
```

- `types.py` imports nothing from `koe`. It is the leaf of the dependency tree.
- `config.py` imports only from `types.py`.
- Every other module imports from `types.py` and optionally `config.py`.
- `main.py` imports from all modules and is the sole orchestrator.
- No module imports from `main.py`. No module imports a peer module's internals.

When two modules need the same data type, that type lives in `types.py`. Modules coordinate through `main.py`'s pipeline, never through direct peer imports. If you find yourself wanting `audio.py` to import from `window.py`, the shared concept belongs in `types.py` and the coordination belongs in `main.py`.

---

## File Organization

> **IMPORTANT**: The project layout tells you where code lives. The file doctrine tells you what a file contains. A file that mixes unrelated concerns is as harmful as code in the wrong module.

### The Rule

**One file = one concern.** Not one type -- one concern. A concern is a pipeline stage or a shared contract that a developer seeks as a unit.

A file may contain multiple TypedDicts if they serve one concern (e.g. all error types in `types.py`). A file must never contain two unrelated pipeline stages. If you struggle to name it, it owns too much.

### When to Split

Split when concerns diverge. Never split to hit a line count.

**Split triggers:**

1. **Distinct concerns.** Two pipeline stages a developer thinks about separately.
2. **Natural duality.** Read/write, encode/decode, capture/playback.
3. **Independent change.** Code changes for a different reason than its neighbours.

**Do NOT split when:**

- The file is "big" but cohesive. Size follows from content, not the reverse.
- You want one type per file. Related types serving one concern share a file.
- Splitting forces readers to jump between files to understand one idea.

### Packages

Koe is a single flat package under `src/koe/`:

- `src/koe/__init__.py` exists and is empty. The package has no public API to re-export -- consumers run the CLI, not import the library.
- `src/koe/py.typed` exists as a PEP 561 typing marker.
- No sub-packages. If a concern needs its own sub-package, the project structure is reconsidered.
- **Module names must not shadow stdlib modules.** `src/koe/types.py` is acceptable because it lives inside the `koe` namespace. A top-level `types.py` would shadow `stdlib.types`.

---

## Naming

Python's PEP 8 naming conventions apply throughout, with these project-specific extensions.

| Code Kind              | Case                   | Example                                    |
| ---------------------- | ---------------------- | ------------------------------------------ |
| Functions              | `snake_case`           | `def check_focused_window()`               |
| Classes / TypedDicts   | `PascalCase`           | `class FocusedWindow(TypedDict)`           |
| Variables              | `snake_case`           | `lock_handle = acquire_instance_lock(...)` |
| Constants              | `SCREAMING_SNAKE_CASE` | `DEFAULT_CONFIG: Final[KoeConfig] = {...}` |
| Modules / packages     | `snake_case`           | `hotkey.py`                                |
| Type aliases           | `PascalCase`           | `type PipelineOutcome = Literal[...]`      |
| `NewType` aliases      | `PascalCase`           | `WindowId = NewType("WindowId", int)`      |
| Private functions      | `_underscore_prefix`   | `def _notification_payload(...)`           |
| Boolean variables      | `is_`/`has_` prefix    | `is_valid`, `has_focus`                    |
| Type parameters        | Single uppercase       | `T`, `E`                                   |

### Domain Naming

| Pattern       | Rule                                                                         |
| ------------- | ---------------------------------------------------------------------------- |
| Module        | The pipeline concern it owns, noun form: `hotkey`, `window`, `notify`        |
| Data type     | The data it represents: `FocusedWindow`, `KoeConfig`, `TranscriptionResult`  |
| Error type    | What went wrong: `FocusError`, `DependencyError`, `InsertionError`           |
| Function      | Verb, imperative: `check`, `acquire`, `send`, `release`                      |
| Type alias    | The domain concept: `PipelineOutcome`, `NotificationKind`, `ExitCode`        |
| NewType       | The domain entity: `WindowId`, `AudioArtifactPath`, `InstanceLockHandle`     |

**Never**: `Manager`, `Handler`, `Service`, `Helper`, `Utils` (over 200 lines), `Base`, `Abstract`, `I`-prefixed. These names describe an architectural role, not a domain concept. A name that describes the domain (`window`, `notify`, `hotkey`) survives refactoring. A name that describes the pattern (`WindowManager`, `NotifyService`) becomes a lie the moment the implementation changes.

---

## Code Style

### Principles

- **Honest signatures.** If a function has side effects, it is not called `get_*`. The signature never lies.
- **Prevent, don't detect.** Make invalid states unrepresentable at the type level. Validate external data at the gate. Assert internal invariants everywhere.
- **Compute, don't remember.** Recompute what is cheap. A cache is hidden state with an invalidation policy you will forget. If you cannot name the invalidation trigger, you cannot have the cache.
- **Return data, not promises.** A pure function is done when it returns. A stateful object is never done -- it is between mutations.

### Conventions

This is a procedural codebase. No class hierarchies, no inheritance, no abstract base classes, no "design patterns" that exist to work around OOP's limitations. If you catch yourself reaching for a base class, a protocol with one implementor, a factory, a strategy pattern, or a visitor -- stop. You are solving a problem that procedural code does not have.

**Domain logic does not live on classes.**

- TypedDicts hold data. They define field names and types. No methods. No properties. No `@classmethod` factories.
- Functions operate on data. They live in modules organised by pipeline concern, not stapled onto the types they happen to use.
- Type aliases and unions define contracts (e.g. `Result[T, E]`, `PipelineOutcome`, `KoeError`), not behaviour hierarchies. Use them for exhaustive narrowing, not for polymorphic dispatch.
- Control flow is explicit. A `match` statement or `if` chain is almost always clearer than dynamic dispatch. When you read a function, you can see every path top to bottom.
- State is a value you pass around, not a property you hide inside an object and mutate through methods.

### Python-Specific Conventions

- **`from __future__ import annotations`** in every file. Enables deferred evaluation of type annotations, avoiding forward-reference issues.
- **`TYPE_CHECKING` guard** for imports used only in type annotations. Prevents circular imports and avoids importing heavyweight modules at runtime when only their types are needed.
- **Positional-only parameters** (`/`) for public API functions that accept config or domain objects. `def acquire_instance_lock(config: KoeConfig, /) -> ...` prevents callers from using keyword syntax, making the API surface explicit.
- **`TypedDict` with `total=True`** for complete records. A missing field is a type error, not a runtime `KeyError`.
- **`Final` for module-level constants.** `DEFAULT_CONFIG: Final[KoeConfig] = {...}` prevents reassignment.
- **`Literal` types for fixed sets.** `whisper_device: Literal["cuda"]` makes CPU fallback a type error.
- **`NewType` for domain opaque aliases.** `WindowId = NewType("WindowId", int)` prevents accidental substitution of arbitrary integers where a window ID is required.
- **`type` statement for type aliases** (PEP 695). `type PipelineOutcome = Literal[...]`.
- **Explicit imports only.** No wildcard imports. Sorted by isort (enforced by ruff `I` rules).
- **Prefer `Result[T, E]` for expected failures.** Callers are forced by Pyright to handle both arms. Exceptions are for programmer bugs only.
- **Three-armed unions when two arms are insufficient.** `TranscriptionResult` has three variants (`text | empty | error`), not `Result[T, E]`, because "no speech" and "error" are distinct user experiences requiring different notifications.

### Python Workarounds

These are current Python/tooling limitations. They will change as Pyright and ruff evolve -- check changelogs when upgrading.

- **Generic TypedDict syntax.** PEP 695 `class Ok[T](TypedDict)` is the desired syntax, but Pyright and ruff may require `class Ok(TypedDict, Generic[T])` with explicit `TypeVar`. Use `# noqa: UP046` / `# noqa: UP040` to suppress ruff's PEP 695 upgrade suggestions when the newer syntax is not yet supported.
- **`cast()` in tests.** Mock return values often need `cast("KoeConfig", {...})` to satisfy Pyright when the mock value is structurally correct but not provably typed.
- **`create=True` on `patch()`.** When patching module-level imports (e.g. `patch("koe.main.shutil.which")`), `create=True` may be needed if the attribute is imported indirectly.

### Module Internal Layout

Follow this section-header pattern for type modules:

```python
"""One sentence description."""

from __future__ import annotations

# ── Domain opaque aliases ──────────────────────────────────────────────────────

# ── Result type ────────────────────────────────────────────────────────────────

# ── Domain-specific types (grouped by concern) ────────────────────────────────

# ── Error types ────────────────────────────────────────────────────────────────

# ── Union type aliases ─────────────────────────────────────────────────────────
```

For pipeline modules:

```python
"""One sentence description."""

from __future__ import annotations

import ...  # stdlib imports

from koe.types import ...  # internal imports

if TYPE_CHECKING:
    from koe.config import KoeConfig  # type-only imports


def public_function(config: KoeConfig, /) -> Result[T, E]:
    """Docstring."""
    ...


def _private_helper(...) -> ...:
    """Docstring."""
    ...
```

### Error Handling

Expected failures return `Result[T, E]`. Programmer bugs raise exceptions.

| Scenario | Mechanism | Example |
|----------|-----------|---------|
| Missing system tool | `Result[None, DependencyError]` | xdotool not installed |
| No focused window | `Result[FocusedWindow, FocusError]` | User has no window active |
| Lock contention | `Result[InstanceLockHandle, AlreadyRunningError]` | Another koe instance running |
| Three-armed outcome | Custom union (`TranscriptionResult`) | text / empty / error |
| Programmer bug | Exception (caught in `main()`) | Wrong type passed to function |

`main()` wraps `run_pipeline()` in `try/except Exception` and maps unhandled exceptions to `ExitCode` 2. Notification emission failures never mask the original exception.

---

## State & Data

> **IMPORTANT**: Bugs are states outside the specification. Every invalid state your type system can represent is a bug waiting to happen. The goal is not to detect invalid states at runtime -- it is to make them unrepresentable. This is not a testing strategy. It is a structural strategy.

**When the code resists, the structure is wrong.** If adding a feature that should be simple is painful, buggy, or requires touching many files -- stop. The pain is signal, not noise. Nearly always the fix is a reorganisation, not more code. Listen to the friction.

### Make Invalid States Unrepresentable

Koe uses Python's type system to eliminate invalid states at the type level:

| Technique | What it prevents | Example |
|-----------|-----------------|---------|
| `Literal` types | Invalid enum-like values | `whisper_device: Literal["cuda"]` -- CPU is a type error |
| `NewType` wrappers | Cross-domain confusion | `WindowId` prevents using an arbitrary `int` as a window ID |
| `TypedDict` with `total=True` | Missing fields | A `KoeConfig` without `sample_rate` is a type error |
| Discriminated unions | Unhandled cases | `Result[T, E]` forces handling both `Ok` and `Err` arms |
| `Literal` discriminants | Ambiguous narrowing | `ok: Literal[True]` / `ok: Literal[False]` enables Pyright narrowing |
| Exhaustive `match` | Forgotten variants | `assert_never(unreachable)` catches unhandled `PipelineOutcome` values |

### Validation at the Gate

External data (subprocess output, environment variables, file contents) is validated at the boundary where it enters the system. Everything past the gate operates on typed values.

```python
# window.py — the gate
window_id_text = window_id_result.stdout.strip()
try:
    window_id = int(window_id_text)
except ValueError:
    return {"ok": False, "error": {"category": "focus", "message": "invalid focused window id"}}

# Past the gate: WindowId is always valid
return {"ok": True, "value": {"window_id": WindowId(window_id), "title": title}}
```

Business logic never contains string parsing, bounds checks, or error handling for values that have already been validated.

### Explicit State, No Hidden Mutation

Koe is single-shot -- state does not survive invocations. Within one invocation:

- Configuration is immutable (`DEFAULT_CONFIG: Final`). Tests override via spread: `{**DEFAULT_CONFIG, "key": value}`.
- Pipeline state flows forward through function returns, not through mutable globals.
- Side effects (lockfile, temp files, clipboard, notifications) are managed in `main.py`'s orchestration, with cleanup in `finally` blocks.
- Resource handles (`InstanceLockHandle`) are acquired and released explicitly, never implicitly.

---

## Verification

### Tests Prove What the Type Checker Cannot See

Pyright strict proves your types are consistent. It cannot prove your values are correct -- that a round-trip preserves data, that subprocess output is parsed correctly, that modules compose to produce the right outcome. Tests exist in the gap between type correctness and value correctness.

Tests in this codebase exist for exactly three purposes:

1. **Behavioural correctness.** The type checker proves types match. Tests prove the computation is right. Exit code mapping, notification payload construction, lock lifecycle, subprocess output parsing.
2. **Cross-boundary contracts.** The type checker sees one module. Tests prove that separately-implemented modules compose correctly -- that a `DependencyError` produced by `dependency_preflight()` is accepted by `send_notification()` and results in the right `PipelineOutcome`.
3. **Runtime properties.** Process exit codes, subprocess behaviour, file lifecycle, notification delivery. Things that only manifest when code executes.

A test that does not fall into one of these three categories is ceremony -- it duplicates what Pyright already guarantees. A test that verifies a function exists, a type constructs, or an import resolves is ceremony. A test that proves `outcome_to_exit_code("success") == 0` is NOT ceremony -- it tests a behavioural contract that Pyright cannot verify.

### Test Conventions

- **`typeguard.check_type`** for runtime shape verification of TypedDict instances. Proves that a value structurally conforms to a type at runtime.
- **`pytest.mark.parametrize`** for exhaustive variant testing. Every `PipelineOutcome` is mapped through `outcome_to_exit_code`. Every error type is checked against its required fields.
- **`unittest.mock.patch`** for subprocess and OS isolation. Tests never call real `xdotool`, `xclip`, or `notify-send`.
- **Descriptive test names**: `test_<function>_<scenario>`. What is being tested and under what conditions.
- **Config overrides via spread**: `{**DEFAULT_CONFIG, "lock_file_path": tmp_path / "koe.lock"}`. Never monkey-patch module globals.

### Asserts Document Invariants, Not Data

When prevention fails and a logic bug slips through, asserts are the last line of defence. They exist to document internal logic invariants: "this result must be Ok here," "this outcome must be one of the controlled set." Never assert on user input, subprocess output, or file contents. Those are data validation, handled at the gate with `Result[T, E]`. An assert that fires is a bug in the code, not bad input.

---

## In-Code Documentation

A clean `make typecheck` and `make lint` pass -- zero warnings, zero errors -- is the baseline. The moment warnings become background noise, real problems hide in them. An agent that sees 60 warnings on every build stops reading them. A build that emits nothing demands attention when it emits something.

### Docstrings

Every public function carries a docstring. When an agent reads a file to understand an API, the docstring is what it sees first -- before implementation, before tests, before AGENTS.md. A missing docstring forces reverse-engineering from code. A wrong docstring is worse than missing.

Docstrings are written by the person or agent who just understood the code. Not in a separate "docs pass" by someone reading cold code. The author of the function writes the docstring -- because they know what it does, what the edge cases are, and what the caller needs to know.

### The Standard

1. **New code ships clean.** Zero Pyright errors, zero ruff warnings from day one.
2. **Touch a file, leave it clean.** When you modify a file, fix any lint or type warnings before committing. The cost is minutes. The alternative is permanent noise.
3. **`ruff format` is the authority** on whitespace and layout. Do not argue with the formatter.

---

## Per-Directory Documentation

Every significant directory has:

- **AGENTS.md** -- rich documentation (purpose, types, function tables, usage, tests). This IS the README. Supported by Cursor, Claude Code, VS Code Copilot, OpenCode.
- **CLAUDE.md** -- thin pointer: `@AGENTS.md`

The `@` reference tells Claude Code to auto-ingest the AGENTS.md file as context.

### AGENTS.md Template

```markdown
# <name>

One sentence: what this does, what input it takes, what output it produces.

**Module**: `koe.<name>`
**Depends on**: [list of modules this uses]

---

## Types

`TypeName(field1, field2, field3)` — what it represents.
`type AliasName = Literal[...]` — what set it models.

---

## Functions

| Function                                        | Description  |
| ----------------------------------------------- | ------------ |
| `module.function_name(ParamType) -> ReturnType` | What it does |

---

## Usage

` ` `python
result = check_focused_window()
if result["ok"]:
    window = result["value"]
` ` `

---

## Design Decisions

[Only if non-obvious. Bold title + paragraph per decision.]

---

## Tests

` ` `bash
make test
# or: uv run pytest tests/test_<name>.py
` ` `

[What test files exist, what they cover]
```

---

## Updating This Document

- When you hit a "where does this go?" question the layout can't answer -> extend the layout
- When a principle leads to a bad outcome -> revise the principle, document why
- When the project structure changes (new modules emerge) -> add the module with its concern
- When Python or tooling evolves (new Pyright features, ruff rules) -> update conventions to match
