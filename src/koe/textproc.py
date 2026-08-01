"""Deterministic transcript cleanup: strip spoken filler words.

Parakeet transcribes verbatim — "um" and "uh" arrive as words, often carrying
their own punctuation ("Um, okay"). This is a pure post-parse pass: no model
knob exists for it, and an LLM pass would trade determinism and latency for
nothing. The verbatim transcript is still archived to the transcription log;
only the text delivered to the clipboard is cleaned.

Conservative by design: only unambiguous disfluencies are removed ("well",
"like", "hmm" can carry intent and are kept), and the text is otherwise left
exactly as dictated — capitalization is repaired only where removing a
sentence-initial filler exposed a lowercase word.
"""

from __future__ import annotations

import re

# u+m+ / u+h+ cover elongations (umm, uhhh); erm/ehm are the same disfluency.
_FILLER_CORE = re.compile(r"^(?:u+m+|u+h+|erm+|ehm+)$", re.IGNORECASE)
_SENTENCE_END = (".", "!", "?")


def strip_filler_words(text: str, /) -> str:
    """Remove filler tokens; repair only the damage the removal causes.

    Token walk over whitespace-separated words:
    - a token whose alphabetic core is a filler is dropped;
    - a sentence-ending mark carried by a dropped filler ("good, um.") moves
      back onto the previous kept word, replacing its trailing comma;
    - a word following a dropped sentence-initial filler is capitalized.
    """
    kept: list[str] = []
    capitalize_next = False
    at_sentence_start = True

    for token in text.split():
        core = token.strip(",.!?;:")
        if _FILLER_CORE.match(core):
            if at_sentence_start:
                capitalize_next = True
            if token.endswith(_SENTENCE_END) and kept:
                kept[-1] = kept[-1].rstrip(",;") + token[-1]
                at_sentence_start = True
                capitalize_next = True
            continue

        kept_token = token[:1].upper() + token[1:] if capitalize_next else token
        capitalize_next = False
        kept.append(kept_token)
        at_sentence_start = kept_token.endswith(_SENTENCE_END)

    return " ".join(kept)
