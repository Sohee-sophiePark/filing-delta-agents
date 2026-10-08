"""Processed corpus → citable passages (consecutive paragraphs merged to a readable size)."""

import json
import pathlib
from dataclasses import dataclass

MIN_CHARS = 400


@dataclass(frozen=True)
class Passage:
    id: str  # id of the first paragraph; the citation key
    ticker: str
    form: str
    filed: str
    period: str
    section: str
    text: str
    url: str
    current: bool  # latest 10-K or a 10-Q filed after it


def filings(processed: pathlib.Path, ticker: str) -> list[dict]:
    """Every processed 10-K/10-Q for `ticker`, newest first."""
    docs = [json.loads(p.read_text()) for p in (processed / ticker).glob("0*.json")]
    return sorted(docs, key=lambda d: d["filed"], reverse=True)


def index(processed: pathlib.Path, ticker: str) -> dict:
    return json.loads((processed / ticker / "index.json").read_text())


def passages(doc: dict, ticker: str, current: bool = True) -> list[Passage]:
    out = []
    for section, paras in doc["sections"].items():
        buf: list[dict] = []
        for p in paras + [None]:
            if p is not None:
                buf.append(p)
            if buf and (p is None or sum(len(b["text"]) + 1 for b in buf) >= MIN_CHARS):
                text = " ".join(b["text"] for b in buf)
                out.append(
                    Passage(
                        buf[0]["id"],
                        ticker,
                        doc["form"],
                        doc["filed"],
                        doc["period"],
                        section,
                        text,
                        doc["url"],
                        current,
                    )
                )
                buf = []
    return out


def load(processed: pathlib.Path, tickers: list[str]) -> list[Passage]:
    out = []
    for t in tickers:
        docs = filings(processed, t)
        latest_k = next(d["filed"] for d in docs if d["form"] == "10-K")
        out += [p for d in docs for p in passages(d, t, d["filed"] >= latest_k)]
    return out
