"""Reply language detection and the post-generation draft check."""
from __future__ import annotations

import pytest

from app.safety import check_draft, detect_language


@pytest.mark.parametrize(
    ("subject", "body", "lang"),
    [
        ("", "سلام، سفارش BZ-123 هنوز نرسیده", "fa"),
        ("", "Where is order BZ-۱۲۳۴۵? It is late.", "en"),
        ("", "salam, sefaresham BZ-391449 hanuz naresideh, lotfan peygiri konid", "fa"),  # Finglish
        ("", "peyk nayomade o status shode delivered, ama man tooye khune boodam", "fa"),
        ("پاسخ ندادن", "I opened a ticket several days ago and have not had any reply.", "en"),  # body decides
        ("Order late", "؟", "en"),                                                     # empty body: subject
        ("", "Hello, the colour is a little different from the photos.", "en"),
        ("", "", "en"),
    ],
)
def test_detect_language(subject: str, body: str, lang: str) -> None:
    assert detect_language(subject, body) == lang


SAFE = [
    ("en", "Thank you for letting us know about order BZ-561342. Our support team is checking the charge "
           "and will get back to you. Feel free to reply here if you have more details. Have a nice day!"),
    ("en", "Thanks for your message. We understand you cannot log in; you can reset your password from the "
           "login page, and our team is looking into the problem."),
    ("fa", "سلام، از پیام شما درباره سفارش BZ-561342 سپاسگزاریم. همکاران ما در حال بررسی موضوع هستند و "
           "به‌زودی با شما تماس می‌گیرند. روز خوبی داشته باشید."),
    ("fa", "سلام، متشکریم که اطلاع دادید. لطفاً شماره سفارش خود را برای ما بفرستید تا موضوع را بررسی کنیم."),
    ("en", "Thanks for asking whether cash on delivery is available in your city; our team is checking."),
    # "متوجه" (understood) contains the letters of "وجه" (funds): found blocking every such draft live
    ("fa", "از تماس شما سپاسگزاریم. متوجه شدیم سفارش BZ-561342 به عنوان تحویل‌شده ثبت شده اما به دست شما "
           "نرسیده است. تیم پشتیبانی در حال بررسی این موضوع است."),
    ("fa", "سلام، ظرفیت ارسال را بررسی می‌کنیم و نتیجه را به شما اطلاع می‌دهیم."),
]


@pytest.mark.parametrize(("lang", "draft"), SAFE)
def test_safe_drafts_pass(lang: str, draft: str) -> None:
    assert check_draft(draft, lang, "", "order BZ-561342") == []


@pytest.mark.parametrize(
    ("lang", "draft", "code"),
    [
        # money, refunds, compensation
        ("en", "We will refund your order right away.", "mentions_money_or_refund"),
        ("en", "Your money will be returned to your card.", "mentions_money_or_refund"),
        ("en", "As a gesture we offer a discount code on your next purchase.", "mentions_money_or_refund"),
        ("en", "We can send a replacement free of charge.", "mentions_money_or_refund"),
        ("fa", "مبلغ سفارش شما به حسابتان واریز می‌شود.", "mentions_money_or_refund"),
        ("fa", "وجه شما به زودی برگشت داده می‌شود.", "mentions_money_or_refund"),
        ("fa", "پول شما برگردانده خواهد شد.", "mentions_money_or_refund"),
        ("fa", "برای جبران، یک کد تخفیف برایتان می‌فرستیم.", "mentions_money_or_refund"),
        ("fa", "هزینه ارسال را ما پرداخت می‌کنیم.", "mentions_money_or_refund"),
        ("fa", "pul shoma bargasht mikhore", "mentions_money_or_refund"),
        # amounts, numbers
        ("en", "The 120,000 toman charge will be reversed.", "contains_number"),
        ("fa", "مبلغ ۷۹۹٬۰۰۰ تومان بررسی شد.", "contains_number"),
        ("en", "Your other order BZ-999 is fine.", "contains_number"),  # not the customer's ref
        # dates, times, durations
        ("en", "Your parcel will arrive tomorrow.", "mentions_date_or_time"),
        ("en", "We will get back to you within two business days.", "mentions_date_or_time"),
        ("en", "Expect an answer by Monday.", "mentions_date_or_time"),
        ("fa", "تا فردا بسته شما می‌رسد.", "mentions_date_or_time"),
        ("fa", "ظرف دو روز کاری پاسخ می‌دهیم.", "mentions_date_or_time"),
        ("fa", "تا پایان هفته پیگیری می‌شود.", "mentions_date_or_time"),
        # promises and things the injection messages ask for
        ("en", "Good news: your full refund has been approved.", "promises_outcome"),
        ("en", "We guarantee the issue will be solved.", "promises_outcome"),
        ("en", "We will replace the item for you.", "promises_outcome"),
        ("fa", "بازپرداخت کامل شما تأیید شده است.", "promises_outcome"),
        ("fa", "کالا را برایتان تعویض می‌کنیم.", "promises_outcome"),
        # links, contacts, secrets
        ("en", "Please verify at https://bazarcheh-refund.example to continue.", "contains_link_or_contact"),
        ("en", "Write to support@bazarcheh.ir for help.", "contains_link_or_contact"),
        ("en", "Please send us your card number so we can check.", "asks_for_sensitive_data"),
        ("fa", "لطفاً رمز عبور خود را برای ما بفرستید.", "asks_for_sensitive_data"),
        # language
        ("fa", "Thanks, we are checking your order.", "wrong_language"),
        ("en", "Thanks, we are checking. سپاس", "wrong_language"),
    ],
)
def test_unsafe_drafts_are_flagged(lang: str, draft: str, code: str) -> None:
    assert code in check_draft(draft, lang, "", "my order BZ-561342")


def test_empty_and_too_long() -> None:
    assert check_draft("   ", "en") == ["empty_draft"]
    assert "too_long" in check_draft("We are checking. " * 100, "en")
