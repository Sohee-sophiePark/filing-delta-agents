"""BM25 keyword retrieval over passages, with metadata filters."""

import math
import re
from collections import Counter

from filing_delta.corpus import Passage

STOP = set(
    "a an and are as at be by for from has have in is it its of on or our that the this to was "
    "we were what which will with".split()
)


# Analyst wording → filing wording, appended to queries before scoring.
SYNONYMS = {
    "revolver": "revolving credit facility",
    "capex": "capital expenditures",
    "buyback": "share repurchase",
    "buying": "repurchase",
    "bond": "notes",
    "bonds": "notes",
    "rated": "credit ratings",
    "planes": "aircraft",
    "late": "delays",
    "contract": "agreement",
    "contracts": "agreements",
    "owe": "debt",
}


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+(?:[.'][a-z0-9]+)*", text.lower()) if t not in STOP]


class BM25:
    def __init__(self, passages: list[Passage], k1: float = 1.5, b: float = 0.75) -> None:
        self.passages, self.k1, self.b = passages, k1, b
        self.tf = [Counter(tokens(p.text)) for p in passages]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = sum(self.len) / max(len(self.len), 1)
        df = Counter(t for c in self.tf for t in c)
        n = len(passages)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, k: int = 5, **where) -> list[tuple[Passage, float]]:
        """Top-k passages; `where` filters on Passage fields (e.g. ticker="DAL", current=True)."""
        q = tokens(query)
        q += [t for w in q if w in SYNONYMS for t in tokens(SYNONYMS[w])]
        scored = []
        for i, p in enumerate(self.passages):
            if any(getattr(p, f) != v for f, v in where.items()):
                continue
            tf, norm = self.tf[i], self.k1 * (1 - self.b + self.b * self.len[i] / self.avg)
            s = sum(
                self.idf.get(t, 0) * tf[t] * (self.k1 + 1) / (tf[t] + norm) for t in q if t in tf
            )
            if s > 0:
                scored.append((p, s))
        return sorted(scored, key=lambda x: -x[1])[:k]
