---
date: 2026-02-20
project: koe-m1
section: 5
status: approved-for-test-design
source_spec: thoughts/projects/2026-02-20-koe-m1/spec.md
source_research: thoughts/projects/2026-02-20-koe-m1/working/section-5-research.md
focus_modules:
  - src/koe/insert.py
  - src/koe/main.py (Section 5 orchestration branch)
---

# Section 5 API Design: Insertion and Clipboard Safety

## Scope

This design is strictly bounded to Section 5 acceptance criteria in `thoughts/projects/2026-02-20-koe-m1/spec.md:82` through `thoughts/projects/2026-02-20-koe-m1/spec.md:87`.

In scope:
- transcript insertion via clipboard write plus simulated paste,
- clipboard backup and restoration contract,
- explicit restore-failure surfacing,
- `main.py` integration for the transcription `kind == "text"` branch.

Out of scope:
- Section 4 transcription behavior,
- notification payload wording enhancements outside insertion paths,
- non-X11 platforms,
- binary clipboard round-trip preservation.

## Existing Contracts Reused

- `InsertionError` in `src/koe/types.py` remains the error payload for all insertion and restore failures.
- `ClipboardState` in `src/koe/types.py` remains the backup payload (`content: str | None`).
- `KoeConfig.paste_key_modifier` and `KoeConfig.paste_key` in `src/koe/config.py` remain the paste trigger configuration.
- `PipelineOutcome` values `success` and `error_insertion` in `src/koe/types.py` remain the orchestration outputs.

No new type aliases are required for Section 5 M1.

## Module Ownership

### `src/koe/insert.py`

Owns all insertion mechanics:
- clipboard read/write,
- paste key simulation,
- restore attempt,
- conversion of subprocess failures into `InsertionError`.

### `src/koe/main.py`

Owns orchestration only:
- call insertion API on transcription text,
- map insertion result to notification and `PipelineOutcome`,
- keep existing cleanup ordering unchanged (artifact cleanup, then lock release).

## API Surface (`insert.py`)

```python
from __future__ import annotations

from koe.config import KoeConfig
from koe.types import ClipboardState, InsertionError, Result


def insert_transcript_text(transcript_text: str, config: KoeConfig, /) -> Result[None, InsertionError]:
    """Insert transcript into focused input via clipboard with restore guarantee."""


def backup_clipboard_text(transcript_text: str, /) -> Result[ClipboardState, InsertionError]:
    """Attempt text clipboard backup before overwrite; returns text or None."""


def write_clipboard_text(text: str, transcript_text: str, /) -> Result[None, InsertionError]:
    """Write UTF-8 text to CLIPBOARD selection."""


def simulate_paste(config: KoeConfig, transcript_text: str, /) -> Result[None, InsertionError]:
    """Trigger configured paste key chord using xdotool."""


def restore_clipboard_text(state: ClipboardState, transcript_text: str, /) -> Result[None, InsertionError]:
    """Restore previous text clipboard state after paste."""
```

### Function Contracts

`insert_transcript_text(transcript_text, config)`
- Validates non-empty text at API edge (`transcript_text.strip() != ""`); empty input returns `Err(InsertionError)`.
- Calls operations in fixed order:
  1. `backup_clipboard_text`
  2. `write_clipboard_text`
  3. `simulate_paste`
  4. `restore_clipboard_text`
- Returns `Ok(None)` only when all four stages succeed.
- Returns `Err(InsertionError)` for any stage failure, including restore-after-paste failure.

`backup_clipboard_text(transcript_text)`
- Must run before any write/paste command.
- Reads clipboard text using X11 text path.
- `Ok({"content": <text>})` when textual clipboard content is readable.
- `Ok({"content": None})` when clipboard has no text or non-text content under M1 text-only boundary.
- `Err(InsertionError)` only for operational failures (subprocess execution/parsing failure).

`write_clipboard_text(text, transcript_text)`
- Writes text to clipboard selection used by paste operation.
- Any write failure returns `Err(InsertionError)` with actionable message.

`simulate_paste(config, transcript_text)`
- Uses `config["paste_key_modifier"] + config["paste_key"]` as the only key chord source.
- Returns `Err(InsertionError)` on simulation failure.

`restore_clipboard_text(state, transcript_text)`
- Restores `state["content"]` exactly when content is `str`.
- For `state["content"] is None`, performs no write and returns `Ok(None)`.
- Any restore command failure returns `Err(InsertionError)`.
- Restore failure is always surfaced to caller even if paste already occurred.

## Clipboard Preservation / Restoration Contract

This is the normative Section 5 contract for M1:

1. Backup attempt is mandatory and ordered before clipboard overwrite.
2. Successful run means: backup completed, write completed, paste completed, restore completed.
3. If restore fails after a successful paste, the run is not considered success.
4. Restore failure must propagate as `error_insertion` so clipboard side effects are never silent.
5. M1 clipboard guarantee is text-only. Non-text clipboard content is represented as `ClipboardState.content = None` and cannot be reconstructed.

## Main Orchestration Integration (`main.py`)

Replace the current Section 5 sentinel branch in `run_pipeline()` with insertion integration.

```python
# after successful transcription_result kind == "text"
insertion_result = insert_transcript_text(transcription_result["text"], config)
if insertion_result["ok"] is False:
    send_notification("error_insertion", insertion_result["error"])
    return "error_insertion"

send_notification("completed")
return "success"
```

Integration rules:
- Existing cleanup `finally` blocks remain unchanged and continue to run on both success and insertion failures.
- No new orchestration state is introduced.
- `error_insertion` remains exit code 1 through existing `outcome_to_exit_code()` mapping.

## Error Message Contract (`InsertionError`)

`InsertionError` payload requirements for all `Err` returns:
- `category`: always `"insertion"`
- `message`: actionable sentence naming failed stage (`backup`, `write`, `paste`, or `restore`)
- `transcript_text`: original transcript text for user/manual recovery

Required message prefixes:
- `"clipboard backup failed:"`
- `"clipboard write failed:"`
- `"paste simulation failed:"`
- `"clipboard restore failed:"`

## Acceptance Criteria Mapping

- AC1 (`spec.md:82`): satisfied by mandatory write + simulated paste sequence in `insert_transcript_text`.
- AC2 (`spec.md:83`): satisfied by `simulate_paste` using configured key chord in X11 target runtime.
- AC3 (`spec.md:84`): satisfied by mandatory pre-write backup and required restore on success path.
- AC4 (`spec.md:85`): satisfied by `Err(InsertionError)` propagation to `main.py` -> `send_notification("error_insertion", ...)` and existing cleanup `finally` boundaries.
- AC5 (`spec.md:86`): satisfied by explicit `restore_clipboard_text` error propagation after paste.
- AC6 (`spec.md:87`): satisfied by explicit text-only contract and `ClipboardState.content = None` non-text limitation.

## Implementation Notes for Section 5 Consumers

- All subprocess calls inside `insert.py` should be `check=False`, capture stderr/stdout, and map command-level failures into `InsertionError`.
- `insert.py` should not send notifications directly; only `main.py` emits user feedback.
- This design intentionally keeps restore failure in the same `error_insertion` channel to avoid expanding notification kinds for M1.
