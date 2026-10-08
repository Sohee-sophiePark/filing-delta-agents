"""Offline evals: retrieval hit@k vs gold passages; risk-factor alignment vs gold pairs."""

import pathlib
import re

import yaml

from filing_delta.corpus import filings
from filing_delta.delta import align
from filing_delta.retrieval import BM25

PREFIX = 80


def retrieval(bm25: BM25, gold_path: pathlib.Path, k: int = 5) -> dict:
    items = yaml.safe_load(gold_path.read_text(encoding="utf-8"))["items"]
    ranks, misses = [], []
    for it in items:
        hits = bm25.search(it["q"], k=k, ticker=it["ticker"], current=True)
        rank = next((i + 1 for i, (p, _) in enumerate(hits) if re.search(it["gold"], p.text)), None)
        ranks.append(rank)
        if rank is None:
            misses.append(f"{it['ticker']}: {it['q']}")
    n = len(items)
    return {
        "n": n,
        "hit@1": sum(r == 1 for r in ranks) / n,
        f"hit@{k}": sum(r is not None for r in ranks) / n,
        "mrr": sum(1 / r for r in ranks if r) / n,
        "misses": misses,
    }


def alignment(processed: pathlib.Path, gold_path: pathlib.Path) -> dict:
    """Pair accuracy, and precision/recall of added + removed, over the gold 10-K pairs."""
    gold = yaml.safe_load(gold_path.read_text(encoding="utf-8"))["pairs"]
    correct = total = tp = fp = fn = 0
    for g in gold:
        docs = {d["accession"]: d for d in filings(processed, g["ticker"])}
        changes = align(docs[g["prior"]]["risk_factors"], docs[g["current"]]["risk_factors"])
        got = {
            c.current["heading"][:PREFIX]: c.prior["heading"][:PREFIX] if c.prior else None
            for c in changes
            if c.current
        }
        got_removed = {c.prior["heading"][:PREFIX] for c in changes if c.status == "removed"}
        for m in g["matches"]:
            total += 1
            correct += got.get(m["current"], "missing") == m["prior"]
        want = {("added", m["current"]) for m in g["matches"] if m["prior"] is None}
        want |= {("removed", h) for h in g["removed"]}
        have = {("added", c) for c, p in got.items() if p is None}
        have |= {("removed", h) for h in got_removed}
        tp, fp, fn = tp + len(want & have), fp + len(have - want), fn + len(want - have)
    return {
        "pairs": total,
        "pair_accuracy": correct / total,
        "added_removed_precision": tp / (tp + fp) if tp + fp else 1.0,
        "added_removed_recall": tp / (tp + fn) if tp + fn else 1.0,
    }
