# koe (声)

Global hotkey speech-to-text. Fully local inference, pipes transcriptions into any focused input.

- **Linux** (Arch X11 / Omarchy Wayland): faster-whisper on NVIDIA CUDA
- **macOS** (Apple Silicon): Parakeet TDT 0.6B on Metal via MLX

## Target scope

- In scope: single-shot toggle flow (invoke, record, invoke again, transcribe, insert, exit)
- Out of scope: daemon mode, streaming preview

## macOS

One key toggles dictation: press to record (bar indicator + timer if SketchyBar
is running), press again to transcribe on the GPU; the transcript lands on the
clipboard and is best-effort pasted at the cursor.

```bash
uv sync
./mac/build.sh          # builds mac/koe.app, signed with a stable local cert
```

Bind any hotkey to `open -gn /path/to/koe/mac/koe.app`. The `open` matters:
LaunchServices makes koe.app the permission "responsibility root", so the
microphone/paste grants attach to koe itself, not to whatever spawned it —
rebind to any launcher without ever re-granting.

First run: click Allow on the microphone prompt (the launcher requests it
natively before recording), and enable koe under System Settings → Privacy &
Security → Accessibility for auto-paste. Paste failure never loses words —
the clipboard always holds the transcript.

Diagnostics: `/tmp/koe.log` (flight recorder — every pipeline state + full
error detail), `~/.local/share/koe/usage.jsonl` (one record per invocation),
`~/.local/share/koe/transcriptions.jsonl` (transcript history).

The first dictation downloads the model (~0.5 GB, one-time). Steady state on
an M4 Pro: model load + Metal warm-up hide inside recording time; a 24 s
utterance transcribes ~0.3 s after the stop press.

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

## Experimental YouTube Bundle

This repo also includes a separate local-only CLI for downloading YouTube audio into a bundle directory under `youtube_artifacts/` without changing the hotkey flow.

Additional system tools:

- `yt-dlp`
- `ffmpeg`

Download only:

```bash
uv run koe-youtube --download-only "<youtube-url>"
```

Download, chunk, and transcribe:

```bash
uv run koe-youtube "<youtube-url>"
```

Default bundle layout:

- `youtube_artifacts/<title-slug>-<video-id>/source/`
- `youtube_artifacts/<title-slug>-<video-id>/audio/full.wav`
- `youtube_artifacts/<title-slug>-<video-id>/chunks/`
- `youtube_artifacts/<title-slug>-<video-id>/transcript.txt`

## Usage log

- Every invocation appends one JSONL record to `/tmp/koe-usage.jsonl`.
- Record shape: `run_id`, `invoked_at`, `outcome`, `duration_ms`.
- No transcript audio or text content is written to this file.
- Clear log history with: `rm /tmp/koe-usage.jsonl`.

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
