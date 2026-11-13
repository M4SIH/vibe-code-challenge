"""Reply language detection and the post-generation safety check for drafts.

Sara's rules: the draft is in the customer's language (fa or en) and never
promises money, refunds, compensation, amounts or dates. The LLM is told the
same, but we do not trust it: every draft is checked here, and anything that
fails is blocked instead of shown.

The check is deliberately strict (it blocks any digit, any money word, any
date/time word), because a blocked draft only costs Sara typing, while an
unsafe one could promise money she never approved.
"""
from __future__ import annotations

import re

from .orders import find_order_ref
from .textnorm import normalize_text

_PERSIAN_LETTER = re.compile(r"[؀-ۿﭐ-﷿ﹰ-﻿]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")
# Common Finglish words (Persian written in Latin letters): those customers get a Persian reply.
_FINGLISH = re.compile(
    r"\b(salam|mersi|merci|lotfan|sefaresh(am|am|e)?|hanuz|hanooz|mikham|mikhastam|konid|konam|shode|"
    r"nashode|nemishe|mishe|chetor|chera|baraye|kheyli|montazeram|peygiri|khaste|nabashid|dorood|"
    r"pulam|pool|pul|ramz|hesab(am)?|kala|baste|tahvil|residam|naresideh|bargardunid|ruz|chikar|"
    r"peyk|nayomad(e|eh)?|nayumade|ama|vali|tooye|tuye|khune(h)?|boodam|budam|hastam|nist|dige|"
    r"kardam|mikonam|bedam|begam|resid(e|eh)?|kharab|taviz|montazer|chie|chiye|bebandid|avaz|"
    r"sabt|shodam|monsaref|faghat|khastam|roshan|nemide|nemiad|mojud|kay|chand)\b",
    re.IGNORECASE,
)


def detect_language(subject: str | None, body: str | None) -> str:
    """'fa' or 'en' for the reply. The body decides (the subject only when the
    body has almost no letters). Order refs, URLs and digits are ignored."""
    def letters(t: str) -> int:
        return len(_PERSIAN_LETTER.findall(t)) + len(_LATIN_LETTER.findall(t))
    text = body or ""
    if letters(text) < 10:
        text = f"{subject or ''} {text}"
    text = re.sub(r"https?://\S+|www\.\S+|BZ\s*-?\s*\d+", " ", text, flags=re.IGNORECASE)
    fa = len(_PERSIAN_LETTER.findall(text))
    latin = len(_LATIN_LETTER.findall(text))
    if fa and fa >= 0.2 * (fa + latin):
        return "fa"
    words = re.findall(r"[A-Za-z]+", text)
    if words and len(_FINGLISH.findall(text)) >= max(2, 0.15 * len(words)):
        return "fa"
    return "en"


# Each rule: (warning code, regex on the normalised draft). normalize_text folds
# Persian/Arabic digits to Latin, Arabic letters to Persian and drops ZWNJ, so
# Persian patterns are written without ZWNJ.
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (code, re.compile("|".join(f"(?:{p})" for p in pats), re.IGNORECASE))
    for code, pats in (
        ("contains_number", (r"\d",)),
        ("mentions_money_or_refund", (
            r"\brefund", r"reimburs", r"compensat", r"money", r"\bcash\b(?! on delivery)", r"\bcredit(ed)?\b",
            r"voucher", r"discount", r"coupon", r"free of charge", r"for free",
            r"\bfree (shipping|delivery|replacement|return)", r"\bpay(ment|ing)? (you|back)",
            r"toman", r"\brials?\b", r"\$|€|£|\birr\b",
            r"تومان", r"ریال", r"\bپول", r"\bوجه\b", r"\bمبلغ", r"استرداد", r"عودت", r"بازپرداخت", r"واریز",
            r"جبران", r"خسارت", r"غرامت", r"کد تخفیف", r"تخفیف", r"اعتبار", r"هزینه",
            r"\bpul\b", r"\bpool\b", r"bargasht",
        )),
        ("mentions_date_or_time", (
            r"\btoday\b", r"\btonight\b", r"tomorrow", r"\bwithin\b", r"\bdeadline", r"business day",
            r"\b(few|couple of|several|next|coming|working|same|two|three|four|five|seven|ten) "
            r"(days?|hours?|weeks?|months?)\b", r"\b(an|one) (hour|day|week|month)\b",
            r"\bby (the )?(end|next|monday|"
            r"tuesday|wednesday|thursday|friday|saturday|sunday)", r"\b(monday|tuesday|wednesday|thursday|"
            r"friday|saturday|sunday)\b", r"\bjanuary|february|march|april|june|july|august|september|"
            r"october|november|december\b", r"\basap\b",
            r"امروز", r"امشب", r"\bفردا", r"\bظرف\b", r"حداکثر", r"ساعت", r"روز کاری", r"روزهای کاری",
            r"\bروز\b(?! خوب| خوش)", r"هفته", r"\bماه\b", r"شنبه", r"جمعه",
            r"فروردین|اردیبهشت|خرداد|تیر ماه|مرداد|شهریور|مهر ماه|آبان|آذر|\bدی ماه|بهمن|اسفند",
        )),
        ("promises_outcome", (
            r"\bguarantee", r"\bpromise", r"\bwe (will|'ll|shall) (replace|send you|exchange|reimburse|"
            r"refund|compensate|credit|cover|deliver it)", r"\bwill be (replaced|refunded|reimbursed|"
            r"credited|compensated|approved)", r"\b(has|have) been (approved|refunded|credited|processed)",
            r"\bapproved\b",
            r"تضمین", r"قول می ?دهیم", r"تعویض (می ?کنیم|خواهد شد|خواهیم کرد)", r"تایید شده|تأیید شده",
            r"بازگردانده (می ?شود|خواهد شد)", r"برگردانده (می ?شود|خواهد شد)",
        )),
        ("contains_link_or_contact", (
            r"https?://", r"\bwww\.", r"\b[a-z0-9-]+\.(com|ir|net|org|example|io)\b", r"@", r"\+98",
        )),
        ("asks_for_sensitive_data", (  # asking for secrets, not merely mentioning a password reset
            r"(send|share|give|provide|tell|enter|confirm|reply with)( us| me)?( your)? (password|pin|cvv2?|otp|"
            r"card number|verification code|one-time code)",
            r"(رمز|شماره کارت|کد تایید|کد یکبار مصرف|cvv).{0,25}(بفرستید|ارسال کنید|بگویید|اعلام کنید|وارد کنید|بنویسید)",
        )),
    )
)


def check_draft(draft: str, language: str, subject: str = "", body: str = "") -> list[str]:
    """Return warning codes; an empty list means the draft may be shown to Sara."""
    text = (draft or "").strip()
    if not text:
        return ["empty_draft"]
    warnings: list[str] = []
    if len(text) > 1200:
        warnings.append("too_long")
    # The customer's own order reference may be repeated back; nothing else with digits.
    ref = find_order_ref(subject) or find_order_ref(body)
    norm = normalize_text(text)
    if ref:
        norm = re.sub(rf"bz\s*-?\s*{ref[3:]}(?!\d)", " ", norm)
    for code, rx in _RULES:
        if rx.search(norm):
            warnings.append(code)
    fa = len(_PERSIAN_LETTER.findall(text))
    latin = len(_LATIN_LETTER.findall(re.sub(r"BZ\s*-?\s*\d+", "", text)))
    if language == "fa" and fa < 0.8 * (fa + latin):
        warnings.append("wrong_language")
    if language == "en" and fa > 0:
        warnings.append("wrong_language")
    return warnings
