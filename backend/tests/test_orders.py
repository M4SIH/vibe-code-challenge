from __future__ import annotations

import pytest

from app.orders import extract_order_ref


def test_order_ref_from_field() -> None:
    assert extract_order_ref("BZ-48219", "") == "BZ-48219"


def test_order_ref_from_body_when_field_empty() -> None:
    assert extract_order_ref("", "my order bz-77310 is late") == "BZ-77310"
    assert extract_order_ref("", "no order mentioned") is None


@pytest.mark.parametrize(
    ("field", "body", "expected"),
    [
        ("BZ-۴۲۷۶۴۸", "", "BZ-427648"),                              # Persian digits
        ("BZ-٣٣٣٩٩٥", "", "BZ-333995"),                              # Arabic-Indic digits
        ("", "کد رهگیری سفارش BZ-۴۲۷۶۴۸ رو که می‌زنم", "BZ-427648"),  # only in the body
        ("", "order BZ-۹۹۸۳۰۱", "BZ-998301"),
        ("", "order BZ 12345 and BZ-999", "BZ-12345"),               # first one wins
        ("BZ-1", "BZ-2", "BZ-1"),                                    # field beats body
        ("", "ABZ-123 is not an order", None),
    ],
)
def test_order_ref_variants(field: str, body: str, expected: str | None) -> None:
    assert extract_order_ref(field, body) == expected


def test_order_ref_from_subject_as_last_resort() -> None:
    assert extract_order_ref("", "where is it?", "Order BZ-555") == "BZ-555"
