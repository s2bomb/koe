# koe (声)

Global hotkey speech-to-text for Linux. Local Whisper inference on GPU, pipes transcriptions into any focused input.

## Target scope

Koe M1 supports Arch Linux on X11 with NVIDIA CUDA local inference.

- In scope: single-shot `make run` flow (invoke, record, transcribe, insert, exit)
- Out of scope: Wayland, macOS, CPU fallback, daemon mode

## Hardware requirements

- NVIDIA GPU with working CUDA runtime
- Microphone input device (usable by the current user)
- Active X11 desktop session

## System prerequisites

- Python 3.12+
- `uv`
- `xdotool`
- `xclip`
- `notify-send` (libnotify)
- PortAudio runtime libraries
- CUDA/cuDNN runtime compatible with your local `faster-whisper` setup

On Arch Linux, install system dependencies before Python packages.

## Install

```bash
uv sync
```

## Verify quality gates

Run these commands in order from a clean shell:

```bash
make lint
make typecheck
make test
```

Expected result: all commands exit 0.

## Run

```bash
make run
```

- On a correctly configured target host, `make run` should complete with exit code 0.
- In a non-target environment (missing X11/CUDA/tools), explicit failure is expected and should be visible in terminal output and/or notification messaging.

## First-run success signals

During a successful run you should observe:

- Notification sequence: recording started -> processing -> completed
- Transcribed text inserted into the focused terminal input
- Clipboard restore intent preserved after insertion

## Troubleshooting

- `no focus`: Ensure a writable terminal window is focused in your X11 session before invoking Koe.
- `missing mic`: Confirm microphone is connected, unmuted, and accessible by the current user.
- `CUDA` unavailable/transcription failure: verify GPU driver, CUDA runtime, and local model runtime compatibility.
- `dependency` failure: install missing tools (`xdotool`, `xclip`, `notify-send`) and retry.

## Release-gate checklist (human verification)

Before Section 7 sign-off on a target host:

1. Validate target runtime happy path: `make run` exits 0 and inserts transcript text.
2. Run a timed cold-start onboarding drill using only this README; confirm first successful transcription in <= 15 minutes.
