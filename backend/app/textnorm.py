"""Text normalisation shared by dedup, order-ref extraction and keyword rules.

Customer text mixes Persian, Arabic and Latin forms of the same characters:
Persian digits (۰-۹) or Arabic-Indic digits (٠-٩) instead of 0-9, Arabic
yeh/kaf (ي ك) instead of Persian (ی ک), zero-width non-joiners inserted at
random, stray RTL/LTR marks, tabs and double spaces.
"""
from __future__ import annotations

import re
import unicodedata

_LETTERS = str.maketrans({
    "ي": "ی",  # Arabic yeh  -> Persian yeh
    "ى": "ی",  # alef maksura -> Persian yeh
    "ك": "ک",  # Arabic kaf  -> Persian keheh
    "ة": "ه",  # teh marbuta -> heh
})

# ZWNJ, ZWJ, ZWSP, LRM, RLM, BOM, bidi embeddings/isolates, tatweel, harakat.
_INVISIBLE = re.compile(
    "[​-‏‪-‮⁦-⁩﻿ـً-ْٰ]"
)
_WHITESPACE = re.compile(r"\s+")


def to_latin_digits(text: str) -> str:
    """Replace every Unicode decimal digit (Persian, Arabic-Indic, ...) by 0-9."""
    return "".join(
        str(unicodedata.decimal(ch)) if not ("0" <= ch <= "9") and unicodedata.decimal(ch, None) is not None
        else ch
        for ch in text
    )


def normalize_text(text: str | None) -> str:
    """Canonical comparison form: NFKC, Latin digits, Persian letters, no
    invisible characters, single spaces, lower case."""
    text = unicodedata.normalize("NFKC", text or "")
    text = to_latin_digits(text).translate(_LETTERS)
    text = _INVISIBLE.sub("", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip().lower()
