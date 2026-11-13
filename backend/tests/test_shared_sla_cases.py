"""The cases file the TypeScript calendar is tested on must match app.sla."""
from __future__ import annotations

import json

import pytest

from scripts.make_sla_cases import OUT, build


def test_shared_cases_are_up_to_date() -> None:
    if not OUT.exists():
        pytest.skip("frontend not available (e.g. inside the backend container)")
    assert json.loads(OUT.read_text(encoding="utf-8")) == build(), \
        "run `python -m scripts.make_sla_cases` from backend/"
