"""Risk-factor changes between two 10-Ks: alignment, change labels, word-level diff."""

import difflib
import re
from dataclasses import dataclass

from filing_delta.retrieval import tokens

THRESHOLD = 0.35
MINOR = 0.05  # share of changed words below which a same-heading change is an update


@dataclass(frozen=True)
class Change:
    status: str  # unchanged | updated | modified | added | removed
    current: dict | None  # risk factor {id, heading, body}
    prior: dict | None
    similarity: float
    changed: float  # share of body words deleted or inserted


def _key(rf: dict) -> set[str]:
    first = re.split(r"(?<=[.!?])\s", rf["body"], maxsplit=1)[0]
    return set(tokens(rf["heading"] + " " + first))


def similarity(a: dict, b: dict) -> float:
    if a["heading"] == b["heading"]:
        return 1.0
    x, y = _key(a), _key(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def align(prior: list[dict], current: list[dict], threshold: float = THRESHOLD) -> list[Change]:
    """Greedy one-to-one pairing by similarity; unpaired items are added or removed."""
    pairs = sorted(
        ((similarity(c, p), i, j) for i, c in enumerate(current) for j, p in enumerate(prior)),
        reverse=True,
    )
    used_c, used_p, out = set(), set(), {}
    for s, i, j in pairs:
        if s < threshold:
            break
        if i in used_c or j in used_p:
            continue
        used_c.add(i)
        used_p.add(j)
        c, p = current[i], prior[j]
        r = changed_share(p["body"], c["body"])
        same_heading = c["heading"] == p["heading"]
        status = (
            "unchanged"
            if same_heading and r == 0
            else "updated"
            if same_heading and r < MINOR
            else "modified"
        )
        out[i] = Change(status, c, p, round(s, 3), round(r, 3))
    changes = [out.get(i) or Change("added", c, None, 0.0, 1.0) for i, c in enumerate(current)]
    gone = [Change("removed", None, p, 0.0, 1.0) for j, p in enumerate(prior) if j not in used_p]
    return changes + gone


def changed_share(old: str, new: str) -> float:
    diff = word_diff(old, new)
    total = len(old.split()) + len(new.split())
    return sum(len(t.split()) for op, t in diff if op != "equal") / total if total else 0.0


def word_diff(old: str, new: str) -> list[tuple[str, str]]:
    """[(op, text)] with op in equal | delete | insert, over whitespace-separated words."""
    a, b = old.split(), new.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op in ("equal", "delete"):
            out.append((op, " ".join(a[i1:i2])))
        elif op == "insert":
            out.append((op, " ".join(b[j1:j2])))
        else:
            out += [("delete", " ".join(a[i1:i2])), ("insert", " ".join(b[j1:j2]))]
    return out
