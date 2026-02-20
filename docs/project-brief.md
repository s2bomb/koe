# PROJECT BRIEF — Koe (声)

## Global Hotkey Voice-to-Text for Linux

**Prepared for:** Brad (CEO)
**Author:** CTO / Project Lead
**Date:** February 2026
**Version:** 1.0

---

## 1. Executive Summary

Koe is a local, GPU-accelerated voice-to-text tool for Arch Linux. It activates via a global hotkey, captures spoken audio, transcribes it using OpenAI Whisper running locally on an RTX 3080 Ti, and inserts the resulting text at the cursor position in any focused application. The system is designed with no persistent daemon; it launches on keypress, processes, delivers text, and exits cleanly.

> **CEO Directive:** Invest heavily in developer experience, clean architecture, and strong typing. Build procedurally and functionally. Avoid loops and OOP where possible. Minimise dependencies. Make the compiler loud about errors. Determinism is the default; state is the explicit exception.

---

## 2. Project Metadata

| Field | Value |
|---|---|
| **Project Name** | Koe (声) |
| **Codename** | koe |
| **Language** | Python (with strict type hints and mypy enforcement) |
| **Target Platform** | Arch Linux (X11 initially, Wayland future consideration) |
| **Hardware Requirement** | NVIDIA RTX 3080 Ti (CUDA-capable GPU) |
| **Transcription Engine** | Faster Whisper (CTranslate2-optimised Whisper) |
| **Architecture** | On-demand process (no daemon) |
| **Paradigm** | Functional / Procedural. Minimal state. No OOP. |
| **Dependency Philosophy** | Minimal. Build from scratch when feasible. |

---

## 3. Problem Statement

Brad works extensively in terminal environments, interacting with LLMs through tools like Claude Code and OpenCode. Typing long-form natural language into these terminal inputs is slow and disruptive to flow. A voice-to-text solution that works globally across any focused input field—terminal, browser, editor—would dramatically improve productivity.

Existing solutions either require cloud APIs (ongoing cost, latency, privacy concerns), are tightly coupled to specific applications, or lack the global hotkey integration needed for a seamless cross-application experience.

---

## 4. Vision and Scope

### 4.1 End-State Vision

Press a single hotkey from any application on the system. If a text input is focused, Koe records speech, transcribes it locally on the GPU, and pastes the transcribed text directly into that input. If no input is detected, the user receives a brief notification. The experience is seamless, universal, and entirely local.

### 4.2 Scope Boundaries

| In Scope | Out of Scope (for now) |
|---|---|
| Global hotkey detection across X11 | Wayland support |
| Audio capture from default microphone | Multi-language transcription |
| Local GPU-accelerated transcription via Faster Whisper | Streaming/real-time word-by-word output |
| Text insertion into focused input field via X11 | Custom vocabulary / fine-tuned models |
| No-input-detected notification | GUI configuration interface |
| Terminal applications (first milestone target) | Mobile or remote access |
| Browser text fields and general X11 inputs | Daemon mode / persistent background process |

---

## 5. Architecture Overview

### 5.1 Core Flow

The system follows a strict linear, procedural pipeline. Each step is a pure function where possible, with side effects isolated and explicit.

| Step | Operation | Side Effect |
|---|---|---|
| 1 | User presses global hotkey | Input event (external) |
| 2 | Detect active window and input field via X11 | X11 query (read-only) |
| 3 | If no input detected: show notification and exit | Desktop notification (write) |
| 4 | Begin audio capture from microphone | Audio device access (read) |
| 5 | User presses hotkey again (or release) to stop recording | Input event (external) |
| 6 | Save audio buffer to temporary WAV file | File write (temp) |
| 7 | Run Faster Whisper inference on GPU | GPU compute (pure transform) |
| 8 | Insert transcribed text at cursor via xdotool/xclip | X11 keyboard simulation (write) |
| 9 | Clean up temp files and exit | File delete (cleanup) |

### 5.2 Text Insertion Strategy

Text insertion will use the X11 clipboard mechanism. The transcribed text is placed into the clipboard, then a Ctrl+V keystroke is simulated via xdotool. This approach works universally across X11 applications, including terminals, browsers, and editors. The original clipboard content is saved beforehand and restored after pasting, so the user's clipboard is not disrupted.

### 5.3 Input Detection Strategy

Use xdotool to query the currently focused window. For the first milestone, the check is simple: if a window is focused, assume it has an input. For future iterations, more granular detection can be layered in using X11 window properties and accessibility APIs.

---

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Language | Python 3.12+ with strict mypy | Mature Whisper ecosystem, rapid iteration, type safety via mypy --strict |
| Transcription | faster-whisper (CTranslate2) | 2–4x faster than vanilla Whisper, lower VRAM usage, local GPU inference |
| Audio Capture | sounddevice (PortAudio binding) | Simple, no-dependency audio capture; direct NumPy integration |
| Hotkey Detection | pynput or evdev | Global keypress detection without root (pynput) or with direct device access (evdev) |
| Window Query | xdotool (subprocess call) | Reliable X11 focused-window detection; no Python dependency needed |
| Text Insertion | xclip + xdotool | Clipboard paste simulation; universal X11 compatibility |
| Notifications | notify-send (subprocess call) | Standard Linux desktop notifications; zero dependencies |
| Build / Lint | mypy --strict, ruff | Compiler-like strictness; fast linting |
| Testing | pytest with typeguard | Runtime type checking in tests for extra safety |

---

## 7. Project Structure

> **Structure Principles:** Flat over nested. Each module is a single file with a clear, singular responsibility. No classes. Functions are pure where possible, with side-effectful functions clearly named and isolated. The structure should be immediately obvious to any developer opening the project for the first time.

```
koe/
├── main.py          — Entry point. Orchestrates the pipeline procedurally. No business logic here.
├── hotkey.py        — Global hotkey registration and listener. Returns key events.
├── audio.py         — Microphone capture. Records to a NumPy buffer. Returns audio data.
├── transcribe.py    — Whisper inference. Takes audio path, returns transcribed string.
├── window.py        — X11 window/input detection. Queries focused window. Returns window info.
├── insert.py        — Text insertion via clipboard + xdotool. Saves/restores clipboard.
├── notify.py        — Desktop notifications via notify-send. Fire-and-forget.
├── config.py        — Configuration constants. Hotkey binding, Whisper model size, audio settings.
└── types.py         — Shared type definitions (TypedDict, NamedTuple, NewType). No logic.

tests/
├── test_audio.py
├── test_transcribe.py
├── test_window.py
├── test_insert.py
└── test_integration.py — End-to-end test of the full pipeline.

pyproject.toml       — Project config, dependencies, mypy and ruff settings.
Makefile             — Common commands: make lint, make typecheck, make test, make run.
README.md            — Setup instructions and usage.
```

---

## 8. Coding Principles (Non-Negotiable)

These principles come directly from the CEO and are foundational to how this project is built. They are not suggestions; they are constraints.

### 8.1 Functional and Procedural First

No classes. No inheritance. No mutable shared state. Functions take inputs and return outputs. Side effects are isolated in clearly-named functions (e.g., `write_to_clipboard`, `send_notification`). The main pipeline reads top-to-bottom like a script.

### 8.2 Strong Typing / Loud Compiler

All code passes `mypy --strict`. Every function has full type annotations, including return types. Use `TypedDict` and `NamedTuple` for structured data instead of plain dicts or tuples. Use `NewType` for domain-specific types (e.g., `AudioPath = NewType('AudioPath', Path)`). The type checker should catch errors before any code runs.

### 8.3 No Loops Where Avoidable

Prefer `map`, `filter`, list comprehensions, and functional transforms over for/while loops. When a loop is genuinely necessary, it should be obvious why, and isolated in its own function with a clear name.

### 8.4 Minimal Dependencies

Every external dependency must justify its existence. If something can be done in 20 lines of code without a library, write those 20 lines. The dependency list should be short and auditable. No frameworks. No "kitchen sink" packages.

### 8.5 Determinism as Default

The same input should always produce the same output. When non-determinism is unavoidable (audio capture, GPU inference timing), it is acknowledged in code comments and contained within a single function boundary.

### 8.6 Clean File System

Flat structure. One file per concern. No nested directories unless the project grows to warrant it. File names describe exactly what the module does.

---

## 9. Milestones

### Milestone 1: Terminal Proof of Concept

This is the target for the project manager to deliver. Everything needed to validate the core concept end-to-end in a terminal environment.

> **Milestone 1 Definition of Done:** User presses a global hotkey while a terminal window is focused. Koe captures audio from the microphone, transcribes it locally on the RTX 3080 Ti using Faster Whisper, and pastes the transcribed text into the terminal input. The full pipeline works, types check, tests pass, and the experience is usable if imperfect.

| Deliverable | Description | Acceptance Criteria |
|---|---|---|
| Hotkey listener | Global key binding that triggers the pipeline from any context | Pressing the configured key starts recording; pressing again stops it |
| Audio capture | Record microphone input to in-memory buffer / temp WAV | Captures clear audio at 16kHz; handles no-mic-found gracefully |
| Whisper transcription | Run faster-whisper on the captured audio using CUDA | Returns accurate English transcription; GPU utilised (not CPU fallback) |
| Text insertion | Paste transcription into the focused terminal via clipboard | Text appears in the terminal input; original clipboard restored |
| Input detection | Check if a window is focused before recording | Shows notification if no window focused; proceeds if window is found |
| Notification feedback | Visual feedback on start/stop/error states | User sees desktop notification for: recording started, processing, error |
| Type safety | Full mypy --strict compliance | `make typecheck` passes with zero errors |
| Tests | Unit tests for each module + one integration test | `make test` passes; covers happy path and key error states |
| Documentation | README with setup instructions | A new developer can install, configure, and run within 15 minutes |

### Milestone 2: Universal Input (Future)

Extend text insertion and input detection to work reliably across browser text fields, code editors, and other X11 applications. Refine the user experience based on Milestone 1 feedback. Not in scope for the project manager's current sprint, but the architecture must not preclude this.

### Milestone 3: Wayland and Polish (Future)

Add Wayland compositor support, consider optional daemon mode if startup latency proves to be a real issue, and explore streaming transcription for a more responsive feel. These are long-horizon items.

---

## 10. Development Environment Setup

The project manager should ensure the following are available on the development machine before beginning work.

### System Dependencies (Arch Linux)

- python 3.12+ (`pacman -S python`)
- CUDA toolkit and cuDNN (`pacman -S cuda cudnn`)
- PortAudio (`pacman -S portaudio`)
- xdotool (`pacman -S xdotool`)
- xclip (`pacman -S xclip`)
- libnotify / notify-send (`pacman -S libnotify`)

### Python Dependencies (pip or pyproject.toml)

- **faster-whisper** — CTranslate2-optimised Whisper inference
- **sounddevice** — Audio capture via PortAudio
- **pynput** — Global hotkey detection
- **numpy** — Audio buffer handling
- **mypy** — Static type checking (dev dependency)
- **ruff** — Linting and formatting (dev dependency)
- **pytest** — Testing framework (dev dependency)

### Hardware

- NVIDIA RTX 3080 Ti with working CUDA drivers
- Functional microphone accessible via PortAudio

---

## 11. Default Configuration

| Setting | Default Value | Notes |
|---|---|---|
| Hotkey | Super+Shift+V (suggestion) | Should be configurable in config.py; choose something unlikely to conflict |
| Whisper model | base.en | Good accuracy/speed tradeoff for English on a 3080 Ti; can upgrade to small.en or medium.en later |
| Audio sample rate | 16000 Hz | Whisper's native sample rate |
| Audio format | float32 WAV | Whisper's expected input format |
| Recording toggle | Press to start, press to stop | Simplest UX; hold-to-talk is a future option |
| Text insertion method | xclip + xdotool Ctrl+V | Universal X11 approach |
| Clipboard restore | Yes | Always restore original clipboard content after paste |

---

## 12. Known Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Hotkey conflict with existing bindings | Medium | Make the hotkey configurable; document common conflicts; test with Arch/i3/sway defaults |
| Whisper model loading time (~2–4s on first run) | Medium | Acceptable for MVP; if painful, consider a lightweight preloading mechanism (not a daemon) |
| xdotool Ctrl+V not working in all terminals | Medium | Some terminals use Ctrl+Shift+V; make paste keystroke configurable in config.py |
| Audio capture fails (no mic, permissions) | High | Detect and notify gracefully on startup; provide clear error messages |
| CUDA not available / fallback to CPU | High | Detect GPU availability at startup; warn user loudly if falling back to CPU |
| X11 assumption breaks on Wayland | Low (for now) | Architecture is modular; window.py and insert.py can be swapped for Wayland equivalents later |

---

## 13. Instructions for the Project Manager

This section is your starting point. Follow these steps to get from this brief to a working Milestone 1.

1. **Set up the project directory** using the structure defined in Section 7. Initialise `pyproject.toml` with the dependencies from Section 10 and configure `mypy --strict` and `ruff` from day one.

2. **Validate the development environment:** confirm CUDA works (`nvidia-smi`), confirm audio capture works (`arecord`), confirm `xdotool` and `xclip` are functional.

3. **Build and test each module independently** in the order listed in Section 5.1 (hotkey, window detection, audio capture, transcription, text insertion, notification). Each module should pass mypy and have at least one unit test before moving to the next.

4. **Wire the modules together** in `main.py` following the procedural pipeline. The main function should read like a step-by-step recipe.

5. **Run the integration test:** press the hotkey in a terminal, speak a sentence, verify the text appears.

6. **Document setup instructions** in `README.md` and confirm a fresh developer can get running in under 15 minutes.

> **Reminder from the CEO:** Always build with global application support in mind, even though Milestone 1 targets terminals only. The architecture should make extending to browsers and editors a matter of adding new detection logic in `window.py` and insertion logic in `insert.py`, not a rewrite.
