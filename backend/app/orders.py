"""Order reference extraction.

Order IDs are ``BZ-`` + digits, but customers type the digits in Persian
(``BZ-۴۲۷۶۴۸``) or Arabic-Indic (``BZ-٣٣٣٩٩٥``) form. We always report the
canonical ``BZ-<Latin digits>``.
"""
from __future__ import annotations

import re

from .textnorm import to_latin_digits

# \d matches any Unicode decimal digit in Python str patterns. The look-arounds
# stop us from picking a ref out of the middle of a longer token.
ORDER_REF_PATTERN = re.compile(r"(?<![A-Za-z])BZ\s*[-_‐-―]?\s*(\d+)", re.IGNORECASE)


def find_order_ref(text: str | None) -> str | None:
    """Return the first order reference in ``text`` as ``BZ-<Latin digits>``."""
    if not text:
        return None
    match = ORDER_REF_PATTERN.search(text)
    if match is None:
        return None
    return f"BZ-{to_latin_digits(match.group(1))}"


def extract_order_ref(order_ref: str | None, body: str | None, subject: str | None = None) -> str | None:
    """Prefer the explicit ``order_ref`` field; fall back to the body, then subject."""
    return find_order_ref(order_ref) or find_order_ref(body) or find_order_ref(subject)
