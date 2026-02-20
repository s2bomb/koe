from __future__ import annotations

from typing import assert_never, assert_type

from koe.transcribe import transcribe_audio
from koe.types import TranscriptionError, TranscriptionResult, TranscriptionText

_TRANSCRIBE_AUDIO = transcribe_audio


def t06_transcription_result_is_closed(result: TranscriptionResult) -> None:
    match result["kind"]:
        case "text":
            assert_type(result["text"], str)
        case "empty":
            return
        case "error":
            assert_type(result["error"], TranscriptionError)
        case _ as unreachable:
            assert_never(unreachable)


def t07_transcription_text_arm_carries_str(result: TranscriptionText) -> None:
    if result["kind"] == "text":
        assert_type(result["text"], str)
