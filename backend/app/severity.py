"""Our own high-severity flag.

The export's ``severity_hint`` is not trustworthy: "Charged twice" and
"account hacked" rows are marked ``low`` while "INVOICE FONT SO UGLY!!!" and
"Careers" are marked ``high``. We therefore decide severity ourselves, using
the README definition of high severity:

* money taken wrongly (charged twice, unauthorised charge, money deducted but
  no order, more than the price deducted, wallet top-up paid but not credited),
* someone else getting into the customer's account,
* a parcel marked delivered (declared lost, or delivered to the wrong address
  or a neighbour) that never reached the customer,
* a product that is actually dangerous.

These keyword rules are the fallback when no LLM is configured. They run on
``normalize_text`` output, so Arabic letters, Persian digits and ZWNJ are
already folded (write Persian patterns without ZWNJ).
"""
from __future__ import annotations

import re

from .textnorm import normalize_text

_RULES: dict[str, tuple[str, ...]] = {
    "wrong_charge": (
        r"charged .{0,40}twice", r"deducted twice", r"twice for (the same|one|my)? ?order",
        r"double charge", r"(did not|didn't|never) authori[sz]e", r"unrecogni[sz]ed charge",
        r"(left|taken from|deducted from|out of) my (account|card).{0,80}(no order|not registered|no confirmation|no order appears)",
        r"was taken from my account, yet no order",
        r"(transaction|charge|payment|deduction).{0,80}(i did not make|i didn't make|not made by me|wasn't me)",
        r"دو ?بار.{0,30}(کسر|برداشت|کم)", r"(کسر|برداشت).{0,30}دو ?بار",
        r"برداشت غیرمجاز", r"انجام نداده ?ام",
        r"(کسر|برداشت|کم) (شده|شد).{0,40}(سفارشی|سفارشم).{0,20}ثبت (نشده|نشد)",
        r"do ?bar.{0,30}(kam|kasr|bardasht)",
        # more than the price taken (not "a higher price showed at checkout": nothing was taken yet)
        r"اضافه ?تر از (حسابم|کارتم) (کسر|برداشت)", r"بیش از قیمت (کسر|برداشت)",
        r"overcharged", r"(more than|above) the (actual |real )?price.{0,40}(deducted|taken|charged)",
        # wallet top-up paid, balance unchanged (questions like "how do I top up" don't match)
        r"(شارژ کردم|sharj kardam|topped up my wallet).{0,60}(موجودی|balance|mojodi)",
        r"شارژ کیف پول اعمال نشد",
    ),
    "account_takeover": (
        r"\bhack(ed)?\b", r"someone (else )?(accessed|logged in|got into|has access)",
        r"login i did not make", r"(unfamiliar|unknown|unrecogni[sz]ed) (device|login)",
        r"phishing",
        r"هک شده", r"کسی وارد حساب", r"دستگاه ناشناس", r"ورود ناشناس",
        r"بدون اطلاع من.{0,20}(عوض|تغییر)", r"شخص دیگری.{0,30}(کنترل|وارد)", r"لینک مشکوک",
        r"hack shode",
    ),
    "not_delivered": (
        r"(marked|shows|showing|status).{0,15}delivered.{0,80}(not|never|nothing|n't)",
        r"declared lost", r"lost in transit", r"lost by the (post|courier)",
        r"تحویل ?شده.{0,30}(ثبت|نشان).{0,60}(نرسیده|دریافت نکرده)",
        r"گم شده", r"مفقود", r"بسته ثبت نشده",
        r"status shode delivered", r"gom shode",
        # delivered somewhere else ("can I ship to a different address?" doesn't match)
        r"(dropped|delivered|left|went) (at|to) (a |the )?(different|wrong) address",
        r"(gave|handed) (it|the parcel|my parcel|the package) to (a |my )?neighbou?r",
        r"به (یک )?آدرس (دیگه|دیگری|اشتباه).{0,20}تحویل (داده|شده)", r"به همسایه (داده|تحویل)",
    ),
    "dangerous_product": (
        r"dangerous", r"fire hazard", r"\bspark", r"\bsmok(e|ed|ing)\b", r"swell|swollen",
        r"electric shock", r"sharp edge", r"burn(t|ing|ed)? smell",
        r"خطرناک", r"جرقه", r"دود کرد", r"باد کرده", r"آتش ?سوزی", r"سوختگی", r"لبه ?های تیز|لبه تیز",
        r"برق گرفت",
        r"khatarnak", r"bad karde", r"jaraghe",
    ),
}
_COMPILED = {name: re.compile("|".join(f"(?:{p})" for p in pats)) for name, pats in _RULES.items()}


def high_severity_reasons(subject: str | None, body: str | None) -> list[str]:
    text = normalize_text(f"{subject or ''} {body or ''}")
    return [name for name, rx in _COMPILED.items() if rx.search(text)]


def is_high_severity_keywords(subject: str | None, body: str | None) -> bool:
    return bool(high_severity_reasons(subject, body))
