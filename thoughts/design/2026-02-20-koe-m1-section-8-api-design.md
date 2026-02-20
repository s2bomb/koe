# Koe M1 Section 8 API Design

## Scope

- Section-only scope: `thoughts/projects/2026-02-20-koe-m1/spec.md` Section 8 acceptance criteria (`AC1`-`AC5`).
- Focus modules only: `src/koe/hotkey.py` integration boundary, `src/koe/main.py` invocation logging hook, and a new `src/koe/usage_log.py` contract.
- Design intent: one Omarchy-triggered invocation maps to exactly one pipeline attempt and exactly one usage-log record.

## Design References

- Spec: `thoughts/projects/2026-02-20-koe-m1/spec.md`
- Research: `thoughts/projects/2026-02-20-koe-m1/working/section-8-research.md`
- Existing runtime contracts: `src/koe/main.py`, `src/koe/hotkey.py`, `src/koe/types.py`, `src/koe/config.py`

## Core Principle

Every Koe invocation writes exactly one structured per-run record before process exit, regardless of outcome (`success`, blocked, expected error, or unexpected exception). Omarchy hotkey integration remains an external trigger contract that launches the same single-shot CLI path.

## Surface A: Omarchy Trigger Integration Boundary (`hotkey.py` + compositor config)

### Contract

- `hotkey.py` remains lock-guard only; no compositor-specific logic is added.
- Omarchy integration is defined as a Hyprland keybinding that runs `koe` exactly once per activation.
- Concurrency behavior is unchanged:
  - first invocation acquires the existing lockfile path;
  - concurrent invocation returns `already_running` via `acquire_instance_lock`.
- Trigger dependency/config failures are represented through existing pipeline outcomes and notifications, then persisted in usage logging.

### Public Python API (unchanged)

```python
def acquire_instance_lock(config: KoeConfig, /) -> Result[InstanceLockHandle, AlreadyRunningError]
def release_instance_lock(handle: InstanceLockHandle, /) -> None
```

### Omarchy binding contract (non-Python artifact)

```conf
bind = SUPER SHIFT, V, exec, koe
```

Invariants:

- One key press launches one process.
- No resident daemon/listener is introduced.
- Section 8 does not implement Wayland focus/insert mechanics (reserved for Section 9).

## Surface B: Per-Run Usage Logging Module (`usage_log.py`)

### New shared type (`types.py`)

```python
class UsageLogRecord(TypedDict):
    run_id: str
    invoked_at: str
    outcome: PipelineOutcome
    duration_ms: int
```

Notes:

- `outcome` reuses `PipelineOutcome` so blocked attempts and all failure modes are type-represented.
- `invoked_at` is ISO-8601 text for JSONL portability and deterministic parsing.

### New config field (`config.py`)

```python
class KoeConfig(TypedDict, total=True):
    ...
    usage_log_path: Path
```

Default contract:

```python
"usage_log_path": Path("/tmp/koe-usage.jsonl")
```

### New module API (`usage_log.py`)

```python
def write_usage_log_record(
    config: KoeConfig,
    outcome: PipelineOutcome,
    /,
    *,
    invoked_at: str,
    duration_ms: int,
) -> None:
    """Append one JSONL usage record; never raise."""
```

Writer contract:

- Append exactly one line per call at `config["usage_log_path"]`.
- Emit JSON object with `run_id`, `invoked_at`, `outcome`, `duration_ms`.
- Generate `run_id` internally as UUID4 string.
- On any write/serialization failure, do not raise; emit a `sys.stderr` diagnostic and return.

## Surface C: Invocation Logging Hook (`main.py`)

### Public API (signatures unchanged)

```python
def main() -> None
def run_pipeline(config: KoeConfig, /) -> PipelineOutcome
def outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode
```

### Behavioral contract update

- `main()` becomes the single logging boundary around `run_pipeline()`.
- `main()` records invocation start time and monotonic start clock before executing `run_pipeline()`.
- `main()` always calls `write_usage_log_record(...)` exactly once before `sys.exit(...)`.
- If `run_pipeline()` raises, `main()` maps to `outcome = "error_unexpected"`, logs that outcome, and exits with code `2`.
- `run_pipeline()` remains focused on pipeline orchestration and notifications only; it does not write usage logs.

### Event ordering contract (normative)

1. Capture `invoked_at` and `start_ms`.
2. Execute `run_pipeline(config)`.
3. Resolve terminal `PipelineOutcome` (return value or `error_unexpected` on exception).
4. Call `write_usage_log_record` exactly once.
5. Exit with `outcome_to_exit_code(outcome)`.

This guarantees one-record-per-invocation, including:

- success,
- no-focus/no-speech,
- dependency/audio/transcription/insertion failures,
- already-running contention,
- unexpected exception in pipeline.

## Section 8 Acceptance Criteria Mapping

| AC | Contract owner | Required behavior |
|---|---|---|
| AC1 Omarchy trigger path | Hyprland binding + CLI entrypoint | Omarchy keybind invokes `koe` without X11 hotkey daemon path |
| AC2 one activation -> one record | `main.py` + `usage_log.py` | Each invocation writes exactly one `UsageLogRecord` |
| AC3 blocked attempts logged distinctly | `hotkey.py` + `PipelineOutcome` + writer | contention returns `already_running`; record outcome is `already_running` |
| AC4 missing trigger deps/config logged | `dependency_preflight` + `main` hook + writer | explicit failure notification plus failed-attempt usage record |
| AC5 testable logging validation | tests + manual Omarchy runbook | automated one-record-per-run assertions + manual runtime confirmation |

## Error Handling Policy

- Expected run failures remain `PipelineOutcome` values and continue to notify the user via existing Section 6 paths.
- Usage logging is best-effort but non-silent:
  - must not crash or alter exit mapping;
  - must emit a stderr diagnostic when record persistence fails.
- Logging failure does not trigger notification dispatch to avoid masking/recursion in degraded dependency states.

## Section 9 Composability Boundary

- Section 8 introduces no focus/insert backend abstraction changes.
- Section 9 may replace focus and insertion adapters (X11/Wayland) while retaining the same per-run logging hook in `main()`.
- Logging contract composes via `PipelineOutcome`; if Section 9 extends outcome variants, type-checking forces exhaustive updates while preserving one-record-per-run semantics.

## Testability Obligations (Section 8)

- `tests/test_main.py`
  - assert `write_usage_log_record` is called exactly once per `main()` invocation;
  - assert ordering: log write happens before `sys.exit`;
  - assert raised exception path logs `error_unexpected`.
- `tests/test_usage_log.py` (new)
  - append behavior (single and multiple writes),
  - runtime shape validation of persisted record,
  - outcome passthrough for all `PipelineOutcome` variants,
  - non-raising behavior with stderr emission on write failures.
- Manual validation artifact (Section 8 working docs)
  - Omarchy keybind activation proof,
  - one JSONL record emitted per activation,
  - contention run includes distinct `already_running` record.
