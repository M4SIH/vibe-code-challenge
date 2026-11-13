# Bazarcheh support dashboard — write-up

**The real problem.** Sara needs to trust two things: what customers struggle with, and what breaks the "2 business hours" promise *right now*. The starter got both wrong: urgency was computed in UTC on a Mon–Fri week with a 24 h SLA, based on a noisy `severity_hint`. The export is also messy: Jalali dates, Persian digits, cosmetic resends, and injection and XSS payloads.

**Assumptions.** Jalali timestamps are Tehran time: in 80 rows mixing Jalali and ISO, reading them as Tehran gives 0 answers-before-receipt, reading them as UTC gives 24%. Tehran is fixed at +03:30. Only the README's 1405 holidays are known. Every row with an id is kept; an unreadable receive time is never urgent and appears as "time unknown". An unreadable `answered_at`, or an answer stamped before receipt, counts as answered. **A resend merges only while the original is unanswered**; the same text after an answer starts a new clock (this surfaced 3 hidden urgent cases). High severity = money taken wrongly (incl. overcharge and a wallet top-up not credited), account takeover, a parcel that never reached the customer (incl. lost, wrong address or neighbour), or a dangerous product. Late refunds, delays and checkout prices are *not* high. Finglish customers get Persian drafts.

**What was wrong and how I found it.** *From reading the code:*
- compose forced a 24 h SLA;
- `sla.py` used UTC (its "normalized upstream" comment was false), Mon–Fri and no holidays, and its test encoded that;
- urgency trusted `severity_hint`;
- drafts were prefetched at upload (burning quota), cached by id, always `"en"`, unchecked, and returned 500 without an LLM;
- one LLM request per message, with no retry;
- `dangerouslySetInnerHTML` was real XSS against the `<img onerror>` rows;
- categories with no messages showed NaN;
- countdowns were in wall-clock minutes.

*From surveying the data:* Jalali rows were dropped, order refs only matched Latin digits, dedup missed ZWNJ, ي/ك and digit-script resends, and the file isn't in time order. *From tests:* an independent minute-by-minute oracle plus planted-bug (mutation) tests caught the loader silently dropping a whitespace-only line, `1405/12/30` silently becoming 1406/01/01, and a token pacer that didn't pace oversized requests. A live test caught the draft check blocking every Persian draft containing "متوجه", which contains "وجه" ("funds").

**What I cut.** Sending, auth, persistence. Negation in the keyword fallback (documented by known-failure tests; not present in the data). Holidays outside 1405. A Playwright suite (instead: Vitest with a frozen clock plus a manual browser pass). Uploads that miss the cache give the LLM 40 s, then fall back to keywords.

**Where the AI misled me.**
1. On 83 hand-labelled messages the LLM scored 100% on severity, but comparing it with the rules on the full exports found 18 breaches of the agreed definition. Prompt v2 fixed them and created a new false alarm; v3 fixed that, yet the LLM still drifts on borderline cases between versions.
2. The keyword rules' "100%" was fitted to the very sample they were written from.
3. The planning notes' "36 answers before receipt" was mostly a parsing artefact; there are 8 real ones.
4. The AI stated a wrong weekday for a date before checking it.
5. The starter's comment "severity_hint is reliable" was false.

**Is the classification good enough?** On 83 sample messages (one per template, labels drafted by the AI and reviewed by me), the LLM's category accuracy is 98.8–100% against 63.9% for keywords. A fresh-cache rerun agreed on 82/83 (95% lower bound 93.5%), and the injection rows were labelled correctly. On the 19-case borderline audit, prompt v3 scores 19/19. Because the LLM drifts on borderline severity, **high = keyword rules OR LLM**: they miss different things, and a false alarm costs Sara a glance while a miss breaks the promise. Reproduce with `python -m eval.evaluate --mode llm [--audit]`. Caveat: the eval export has no labels.

**Are AI replies safe to show Sara?**
- Drafts are made only on click.
- Customer text is passed to the LLM as JSON inside `<customer_message>`, with rules to ignore instructions in it.
- The prompt forbids money, refunds, amounts, dates, promises, links and requests for secrets.
- **Every draft is then checked deterministically** (`app/safety.py`, fa/en/Finglish) for: digits (except the customer's own order ref), money or refund words, dates or durations, promise phrases, links or contacts, requests for passwords or cards, and the wrong language. A failing draft gets one retry, then it is blocked.
- Any failure → `200 {"blocked": true}`, never a hang or 500.
- Sara edits in a textarea and approves (copy only).

Evidence: 46 validator tests, 12 endpoint tests with a misbehaving fake LLM, and 15 live drafts on real messages including all injection variants. None promised a refund, an approval or a link.

*Run:* `docker compose up` → http://localhost:5173 · tests: `pytest` (896), `npm test` (1,254) · the LLM cache for both exports ships in `backend/.cache/`, so `docker compose up` reproduces these results with no `.env` or key.
