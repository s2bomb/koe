from __future__ import annotations

from koe.textproc import strip_filler_words


def test_strips_sentence_initial_filler_and_recapitalizes() -> None:
    assert strip_filler_words("Um, okay so left click is working.") == (
        "Okay so left click is working."
    )


def test_strips_mid_sentence_fillers_preserving_flow() -> None:
    assert strip_filler_words("hold option and then, um, left click is, uh, working") == (
        "hold option and then, left click is, working"
    )


def test_strips_elongated_fillers() -> None:
    assert strip_filler_words("Ummm okay. Uhhh sure.") == "Okay. Sure."


def test_keeps_intentful_words() -> None:
    text = "Well, I like this, hmm, maybe."
    assert strip_filler_words(text) == text


def test_does_not_touch_words_containing_filler_substrings() -> None:
    text = "The aluminum drum hummed."
    assert strip_filler_words(text) == text


def test_filler_only_input_becomes_empty() -> None:
    assert strip_filler_words("Um. Uh, um.") == ""


def test_untouched_text_passes_through_exactly() -> None:
    """No fillers -> byte-identical output; mid-sentence cursor insertions
    must never get surprise capitalization or punctuation edits."""
    text = "hello world, this stays lowercase. And this stays as-is."
    assert strip_filler_words(text) == text


def test_sentence_final_filler_moves_terminal_punctuation_back() -> None:
    assert strip_filler_words("that's really good, um.") == "that's really good."


def test_real_dictation_sample_reads_clean() -> None:
    """Brad's first real dictation, 2026-08-01 — the fixture that motivated this."""
    raw = (
        "Um okay so left click sorry um hold option and then left click is working "
        "um in terms of it's hovering it's dragging and that's really good."
    )
    assert strip_filler_words(raw) == (
        "Okay so left click sorry hold option and then left click is working "
        "in terms of it's hovering it's dragging and that's really good."
    )
