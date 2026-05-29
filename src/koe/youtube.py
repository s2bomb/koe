"""YouTube audio download, chunking, and local transcript export."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, TypedDict, cast

from koe.config import DEFAULT_CONFIG
from koe.types import AudioArtifactPath, Result

if TYPE_CHECKING:
    from koe.config import KoeConfig


_DEFAULT_OUTPUT_ROOT: Final[Path] = Path.cwd() / "youtube_artifacts"
_MAX_TITLE_SLUG_LENGTH: Final[int] = 80
_SENTENCE_BOUNDARY_RE: Final[re.Pattern[str]] = re.compile(r"(?<=[.!?])\s+")
_WORD_EDGE_RE: Final[re.Pattern[str]] = re.compile(r"(^\W+)|(\W+$)")

_progress_to_stderr: bool = False


def _progress(message: str, /) -> None:
    """Print a progress message, routing to stderr in stdout-pipe mode."""
    print(message, file=sys.stderr if _progress_to_stderr else sys.stdout)


class YoutubeError(TypedDict):
    category: Literal["youtube"]
    message: str


class YoutubeVideoInfo(TypedDict):
    video_id: str
    title: str
    webpage_url: str


class YoutubeBundlePaths(TypedDict):
    bundle_dir: Path
    source_dir: Path
    audio_dir: Path
    chunks_dir: Path
    metadata_path: Path
    source_template_path: Path
    normalized_audio_path: Path
    transcript_path: Path
    raw_transcript_path: Path


def main() -> None:
    """Run the standalone YouTube download and transcription CLI."""
    global _progress_to_stderr  # noqa: PLW0603

    args = _parse_args()

    if args.to_stdout:
        _progress_to_stderr = True
        if args.download_only:
            print("--to-stdout is incompatible with --download-only", file=sys.stderr)
            sys.exit(1)

    result = run_youtube_pipeline(
        args.url,
        args.output_root,
        chunk_seconds=args.chunk_seconds,
        overlap_seconds=args.overlap_seconds,
        download_only=args.download_only,
        whisper_model=args.whisper_model,
        max_overlap_words=args.max_overlap_words,
    )
    if result["ok"] is False:
        print(result["error"]["message"], file=sys.stderr)
        sys.exit(1)

    if args.to_stdout:
        transcript_path = result["value"] / "transcript.txt"
        sys.stdout.write(transcript_path.read_text(encoding="utf-8"))
    else:
        print(f"bundle ready: {result['value']}")
    sys.exit(0)


def run_youtube_pipeline(  # noqa: PLR0913, PLR0911
    url: str,
    output_root: Path,
    /,
    *,
    chunk_seconds: int,
    overlap_seconds: float,
    download_only: bool,
    whisper_model: str | None,
    max_overlap_words: int,
) -> Result[Path, YoutubeError]:
    """Download YouTube audio into a local bundle and optionally transcribe it."""
    validation = _validate_options(chunk_seconds, overlap_seconds, max_overlap_words)
    if validation["ok"] is False:
        return validation

    dependencies = _dependency_preflight()
    if dependencies["ok"] is False:
        return dependencies

    video_info_result = _inspect_video(url)
    if video_info_result["ok"] is False:
        return video_info_result
    video_info = video_info_result["value"]

    bundle_paths = _prepare_bundle_paths(output_root, video_info["title"], video_info["video_id"])
    metadata: dict[str, object] = {
        "video_id": video_info["video_id"],
        "title": video_info["title"],
        "url": video_info["webpage_url"],
        "chunk_seconds": chunk_seconds,
        "overlap_seconds": overlap_seconds,
        "download_only": download_only,
        "whisper_model": whisper_model or DEFAULT_CONFIG["whisper_model"],
    }
    _write_metadata(bundle_paths["metadata_path"], metadata)

    _progress(f"Inspecting: {video_info['title']}")

    source_result = _download_source_audio(video_info["webpage_url"], bundle_paths)
    if source_result["ok"] is False:
        return source_result
    source_path = source_result["value"]
    metadata["source_audio_path"] = str(source_path)

    normalize_result = _normalize_audio(source_path, bundle_paths["normalized_audio_path"])
    if normalize_result["ok"] is False:
        return normalize_result
    metadata["normalized_audio_path"] = str(bundle_paths["normalized_audio_path"])

    if download_only:
        _write_metadata(bundle_paths["metadata_path"], metadata)
        return {"ok": True, "value": bundle_paths["bundle_dir"]}

    chunk_result = chunk_wav_audio(
        bundle_paths["normalized_audio_path"],
        bundle_paths["chunks_dir"],
        chunk_seconds=chunk_seconds,
        overlap_seconds=overlap_seconds,
    )
    if chunk_result["ok"] is False:
        return chunk_result
    chunk_paths = chunk_result["value"]
    metadata["chunk_count"] = len(chunk_paths)

    config = _transcription_config(whisper_model)
    transcript_result = _transcribe_chunks(chunk_paths, config, max_overlap_words)
    if transcript_result["ok"] is False:
        return transcript_result

    raw_transcript = transcript_result["value"]
    formatted_transcript = format_transcript_lines(raw_transcript)
    bundle_paths["raw_transcript_path"].write_text(f"{raw_transcript}\n", encoding="utf-8")
    bundle_paths["transcript_path"].write_text(f"{formatted_transcript}\n", encoding="utf-8")
    metadata["raw_transcript_path"] = str(bundle_paths["raw_transcript_path"])
    metadata["transcript_path"] = str(bundle_paths["transcript_path"])
    _write_metadata(bundle_paths["metadata_path"], metadata)
    return {"ok": True, "value": bundle_paths["bundle_dir"]}


def chunk_wav_audio(
    audio_path: Path,
    output_dir: Path,
    /,
    *,
    chunk_seconds: int,
    overlap_seconds: float,
) -> Result[list[Path], YoutubeError]:
    """Split a normalized WAV file into overlapping chunk WAV files."""
    _clear_generated_chunks(output_dir)
    try:
        with wave.open(str(audio_path), "rb") as source_handle:
            sample_rate = source_handle.getframerate()
            channel_count = source_handle.getnchannels()
            sample_width = source_handle.getsampwidth()
            total_frames = source_handle.getnframes()

            chunk_frames = max(1, int(chunk_seconds * sample_rate))
            overlap_frames = max(0, int(overlap_seconds * sample_rate))
            step_frames = chunk_frames - overlap_frames
            if step_frames <= 0:
                return {
                    "ok": False,
                    "error": _youtube_error("overlap must be smaller than chunk size"),
                }

            chunk_paths: list[Path] = []
            for index, start_frame in enumerate(range(0, total_frames, step_frames), start=1):
                source_handle.setpos(start_frame)
                frames = source_handle.readframes(min(chunk_frames, total_frames - start_frame))
                if frames == b"":
                    break

                chunk_path = output_dir / f"chunk-{index:04d}.wav"
                with wave.open(str(chunk_path), "wb") as chunk_handle:
                    chunk_handle.setnchannels(channel_count)
                    chunk_handle.setsampwidth(sample_width)
                    chunk_handle.setframerate(sample_rate)
                    chunk_handle.writeframes(frames)
                chunk_paths.append(chunk_path)

                if start_frame + chunk_frames >= total_frames:
                    break
    except (OSError, wave.Error) as error:
        return {"ok": False, "error": _youtube_error(f"wav chunking failed: {error}")}

    if len(chunk_paths) == 0:
        return {"ok": False, "error": _youtube_error("wav chunking produced no audio chunks")}
    return {"ok": True, "value": chunk_paths}


def format_transcript_lines(transcript_text: str, /, max_words_per_line: int = 18) -> str:
    """Format transcript text into sentence-oriented lines."""
    stripped_text = transcript_text.strip()
    if stripped_text == "":
        return ""

    sentences = [sentence.strip() for sentence in _SENTENCE_BOUNDARY_RE.split(stripped_text)]
    non_empty_sentences = [sentence for sentence in sentences if sentence != ""]
    if len(non_empty_sentences) == 0:
        return ""

    lines: list[str] = []
    for sentence in non_empty_sentences:
        words = sentence.split()
        if len(words) <= max_words_per_line:
            lines.append(" ".join(words))
            continue
        lines.extend(_wrap_words(words, max_words_per_line))

    return "\n".join(lines)


def merge_chunk_transcripts(chunk_texts: list[str], /, *, max_overlap_words: int) -> str:
    """Merge chunk transcripts while dropping duplicated overlap words."""
    merged_text = ""
    for chunk_text in chunk_texts:
        normalized_chunk = " ".join(chunk_text.split())
        if normalized_chunk == "":
            continue
        if merged_text == "":
            merged_text = normalized_chunk
            continue

        merged_text = _merge_text_pair(
            merged_text,
            normalized_chunk,
            max_overlap_words=max_overlap_words,
        )
    return merged_text


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="YouTube video URL to download and transcribe")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=_DEFAULT_OUTPUT_ROOT,
        help=f"Bundle root directory (default: {_DEFAULT_OUTPUT_ROOT})",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=int,
        default=30,
        help="Chunk duration in seconds before transcription (default: 30)",
    )
    parser.add_argument(
        "--overlap-seconds",
        type=float,
        default=1.0,
        help="Chunk overlap in seconds for boundary safety (default: 1.0)",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download source audio and normalized WAV bundle without transcribing",
    )
    parser.add_argument(
        "--whisper-model",
        default=None,
        help=f"Optional Whisper model override (default: {DEFAULT_CONFIG['whisper_model']})",
    )
    parser.add_argument(
        "--max-overlap-words",
        type=int,
        default=12,
        help="Maximum duplicated words to trim when merging chunk transcripts (default: 12)",
    )
    parser.add_argument(
        "--to-stdout",
        action="store_true",
        help="Print formatted transcript to stdout (progress messages route to stderr)",
    )
    return parser.parse_args()


def _validate_options(
    chunk_seconds: int, overlap_seconds: float, max_overlap_words: int, /
) -> Result[None, YoutubeError]:
    if chunk_seconds <= 0:
        return {"ok": False, "error": _youtube_error("chunk_seconds must be positive")}
    if overlap_seconds < 0:
        return {"ok": False, "error": _youtube_error("overlap_seconds must be non-negative")}
    if overlap_seconds >= chunk_seconds:
        return {
            "ok": False,
            "error": _youtube_error("overlap_seconds must be smaller than chunk_seconds"),
        }
    if max_overlap_words < 0:
        return {"ok": False, "error": _youtube_error("max_overlap_words must be non-negative")}
    return {"ok": True, "value": None}


def _dependency_preflight() -> Result[None, YoutubeError]:
    required_tools = ["yt-dlp", "ffmpeg"]
    for tool in required_tools:
        if shutil.which(tool) is None:
            return {"ok": False, "error": _youtube_error(f"required tool is missing: {tool}")}
    return {"ok": True, "value": None}


def _inspect_video(url: str, /) -> Result[YoutubeVideoInfo, YoutubeError]:
    command = ["yt-dlp", "--dump-single-json", "--no-download", "--no-playlist", url]
    command_result = _run_command(command, error_prefix="video inspection failed")
    if command_result["ok"] is False:
        return command_result

    try:
        payload = json.loads(command_result["value"])
    except json.JSONDecodeError as error:
        return {
            "ok": False,
            "error": _youtube_error(f"video inspection returned invalid JSON: {error}"),
        }

    video_id = payload.get("id")
    title = payload.get("title")
    webpage_url = payload.get("webpage_url", url)
    if not isinstance(video_id, str) or video_id == "":
        return {"ok": False, "error": _youtube_error("video inspection did not return an id")}
    if not isinstance(title, str) or title == "":
        return {"ok": False, "error": _youtube_error("video inspection did not return a title")}
    if not isinstance(webpage_url, str) or webpage_url == "":
        webpage_url = url

    return {"ok": True, "value": {"video_id": video_id, "title": title, "webpage_url": webpage_url}}


def _prepare_bundle_paths(output_root: Path, title: str, video_id: str, /) -> YoutubeBundlePaths:
    bundle_dir = resolve_bundle_dir(output_root, title, video_id)
    source_dir = bundle_dir / "source"
    audio_dir = bundle_dir / "audio"
    chunks_dir = bundle_dir / "chunks"
    for directory in (bundle_dir, source_dir, audio_dir, chunks_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return {
        "bundle_dir": bundle_dir,
        "source_dir": source_dir,
        "audio_dir": audio_dir,
        "chunks_dir": chunks_dir,
        "metadata_path": bundle_dir / "metadata.json",
        "source_template_path": source_dir / "source.%(ext)s",
        "normalized_audio_path": audio_dir / "full.wav",
        "transcript_path": bundle_dir / "transcript.txt",
        "raw_transcript_path": bundle_dir / "transcript_raw.txt",
    }


def resolve_bundle_dir(output_root: Path, title: str, video_id: str, /) -> Path:
    """Resolve the friendly bundle path and migrate legacy video-id-only bundles."""
    desired_bundle_dir = output_root / bundle_dir_name(title, video_id)
    legacy_bundle_dir = output_root / video_id
    if legacy_bundle_dir.exists() and not desired_bundle_dir.exists():
        legacy_bundle_dir.rename(desired_bundle_dir)
    return desired_bundle_dir


def bundle_dir_name(title: str, video_id: str, /) -> str:
    """Build a friendly bundle directory name from title slug and video id."""
    title_slug = _slugify_title(title)
    return f"{title_slug}-{video_id}"


def _slugify_title(title: str, /) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    collapsed = re.sub(r"[^A-Za-z0-9]+", "-", ascii_title).strip("-").lower()
    if collapsed == "":
        return "video"
    if len(collapsed) <= _MAX_TITLE_SLUG_LENGTH:
        return collapsed
    truncated = collapsed[:_MAX_TITLE_SLUG_LENGTH].rstrip("-")
    return truncated or "video"


def _download_source_audio(
    url: str, bundle_paths: YoutubeBundlePaths, /
) -> Result[Path, YoutubeError]:
    existing_source = _locate_source_audio(bundle_paths["source_dir"])
    if existing_source["ok"] is True:
        _progress(f"Reusing source audio: {existing_source['value']}")
        return existing_source

    _progress("Downloading source audio with yt-dlp")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--no-progress",
        "-f",
        "worstaudio/bestaudio",
        "-o",
        str(bundle_paths["source_template_path"]),
        url,
    ]
    command_result = _run_command(command, error_prefix="audio download failed")
    if command_result["ok"] is False:
        return command_result
    return _locate_source_audio(bundle_paths["source_dir"])


def _locate_source_audio(source_dir: Path, /) -> Result[Path, YoutubeError]:
    candidates = sorted(
        path
        for path in source_dir.glob("source.*")
        if path.is_file() and path.suffix not in {".part", ".tmp", ".ytdl"}
    )
    if len(candidates) == 0:
        return {
            "ok": False,
            "error": _youtube_error("source audio file was not found after download"),
        }
    return {"ok": True, "value": candidates[0]}


def _normalize_audio(source_path: Path, output_path: Path, /) -> Result[None, YoutubeError]:
    _progress("Normalizing audio to 16 kHz mono WAV")
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    command_result = _run_command(command, error_prefix="audio normalization failed")
    if command_result["ok"] is False:
        return command_result
    return {"ok": True, "value": None}


def _transcription_config(whisper_model: str | None, /) -> KoeConfig:
    if whisper_model is None:
        return DEFAULT_CONFIG
    return cast("KoeConfig", {**DEFAULT_CONFIG, "whisper_model": whisper_model})


def _transcribe_chunks(
    chunk_paths: list[Path], config: KoeConfig, max_overlap_words: int, /
) -> Result[str, YoutubeError]:
    from koe.transcribe import (  # noqa: PLC0415
        load_transcription_model,
        transcribe_audio_with_model,
    )

    model_result = load_transcription_model(config)
    if model_result["ok"] is False:
        return {"ok": False, "error": _youtube_error(model_result["error"]["message"])}
    model = model_result["value"]

    chunk_texts: list[str] = []
    chunk_count = len(chunk_paths)
    for index, chunk_path in enumerate(chunk_paths, start=1):
        _progress(f"Transcribing chunk {index}/{chunk_count}: {chunk_path.name}")
        transcription_result = transcribe_audio_with_model(model, AudioArtifactPath(chunk_path))
        if transcription_result["kind"] == "error":
            return {"ok": False, "error": _youtube_error(transcription_result["error"]["message"])}

        chunk_text = "" if transcription_result["kind"] == "empty" else transcription_result["text"]
        chunk_texts.append(chunk_text)
        chunk_path.with_suffix(".txt").write_text(f"{chunk_text}\n", encoding="utf-8")

    merged_text = merge_chunk_transcripts(chunk_texts, max_overlap_words=max_overlap_words)
    if merged_text == "":
        return {"ok": False, "error": _youtube_error("transcription produced no text")}
    return {"ok": True, "value": merged_text}


def _run_command(command: list[str], /, *, error_prefix: str) -> Result[str, YoutubeError]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as error:
        return {"ok": False, "error": _youtube_error(f"{error_prefix}: {error}")}

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        return {"ok": False, "error": _youtube_error(f"{error_prefix}: {detail}")}
    return {"ok": True, "value": result.stdout}


def _clear_generated_chunks(output_dir: Path, /) -> None:
    for existing_path in output_dir.glob("chunk-*"):
        if existing_path.is_file():
            existing_path.unlink()


def _wrap_words(words: list[str], max_words_per_line: int, /) -> list[str]:
    return [
        " ".join(words[index : index + max_words_per_line])
        for index in range(0, len(words), max_words_per_line)
    ]


def _merge_text_pair(left_text: str, right_text: str, /, *, max_overlap_words: int) -> str:
    left_words = left_text.split()
    right_words = right_text.split()
    overlap_count = 0
    max_window = min(max_overlap_words, len(left_words), len(right_words))
    for window_size in range(max_window, 0, -1):
        left_window = [_canonical_word(word) for word in left_words[-window_size:]]
        right_window = [_canonical_word(word) for word in right_words[:window_size]]
        if left_window == right_window:
            overlap_count = window_size
            break

    merged_words = left_words + right_words[overlap_count:]
    return " ".join(merged_words)


def _canonical_word(word: str, /) -> str:
    normalized_word = _WORD_EDGE_RE.sub("", word).lower()
    if normalized_word == "":
        return word.lower()
    return normalized_word


def _write_metadata(path: Path, metadata: dict[str, object], /) -> None:
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _youtube_error(message: str, /) -> YoutubeError:
    return {"category": "youtube", "message": message}
