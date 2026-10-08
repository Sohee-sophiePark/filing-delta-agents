"""Deterministic output gates: citations exist, numbers traceable, no advice, valid status."""

import re

PLACEHOLDER = re.compile(r"\{\{m:([a-z0-9_.]+)\}\}")
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
ALLOWED_DIGITS = re.compile(  # dates, years, form names, identifiers (PSP3, A321neo), Boeing models
    rf"\b{MONTH} \d{{1,2}}\b|\b(?:19|20)\d\d\b|\b(?:10-K|10-Q|8-K)\b|\bItem \d+[A-C]?\b"
    r"|\b[A-Z]+\d+[A-Za-z]*\b|\bBoeing 7\d7\b|\b7\d7 MAX\b"
)
ADVICE = re.compile(
    r"\b(buy|sell|hold|overweight|underweight|price target|invest in|"
    r"we recommend (?:buying|selling))\b",
    re.I,
)


NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def bullet_issues(
    b: dict, evidence: dict[str, str], metric_keys: set[str], signal_ids: set[str]
) -> list[str]:
    issues = []
    cites, ms, sigs = b.get("citations", []), b.get("metrics", []), b.get("signals", [])
    if not cites and not ms and not sigs:
        issues.append("no citation, metric or signal")
    issues += [f"unknown signal {s}" for s in sigs if s not in signal_ids]
    issues += [f"unknown citation {c}" for c in cites if c not in evidence]
    issues += [f"unknown metric {m}" for m in ms if m not in metric_keys]
    issues += [
        f"unknown metric {m}" for m in PLACEHOLDER.findall(b["text"]) if m not in metric_keys
    ]
    cited = " ".join(evidence.get(c, "") for c in cites)
    for n in NUMBER.findall(ALLOWED_DIGITS.sub("", PLACEHOLDER.sub("", b["text"]))):
        if n not in cited:
            issues.append(
                f"number {n} is not in the cited evidence; use a {{{{m:KEY}}}} placeholder"
            )
    if ADVICE.search(b["text"]):
        issues.append("investment-advice wording")
    return issues


def check(
    bullets: list[dict],
    evidence: dict[str, str],
    metric_keys: set[str],
    signal_ids: set[str] = frozenset(),
) -> list[str]:
    """Gate failures as 'n: issue' strings (n is the 1-based bullet number).

    A number may appear as a {{m:KEY}} placeholder or quoted exactly from a cited evidence text.
    """
    return [
        f"{n}: {i}"
        for n, b in enumerate(bullets, 1)
        for i in bullet_issues(b, evidence, metric_keys, signal_ids)
    ]


def status_issue(status: str, allowed: set[str]) -> list[str]:
    return (
        []
        if status in allowed
        else [f"status {status!r} not allowed by signals; use one of {sorted(allowed)}"]
    )
