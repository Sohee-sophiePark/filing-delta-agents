"""Filing HTML → text blocks → Items (1A, 7, 7A, …) and Item 1A risk factors."""

import re
from dataclasses import dataclass
from html.parser import HTMLParser

ITEM = re.compile(r"^item\s*(\d{1,2}[a-c]?)\s*[.:\-–—]?\s", re.I)
NOTE = re.compile(r"^(?:note\s*)?\d{1,2}\s*[.:\-–—]\s+([a-z].*)", re.I)


@dataclass(frozen=True)
class Block:
    text: str
    emphasis: float  # share of characters in bold or italic


@dataclass(frozen=True)
class RiskFactor:
    heading: str
    body: str


class _Blocks(HTMLParser):
    BREAK = {"div", "p", "tr", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "table"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, bool]] = []
        self.blocks: list[Block] = []
        self.cur: list[tuple[str, bool]] = []
        self.hidden = 0

    def flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(t for t, _ in self.cur)).strip()
        if text:
            emph = sum(len(t.strip()) for t, e in self.cur if e)
            self.blocks.append(Block(text, emph / len(re.sub(r"\s", "", text) or "x")))
        self.cur = []

    def handle_starttag(self, tag, attrs):
        if tag == "ix:header":
            self.hidden += 1
        if tag in self.BREAK:
            self.flush()
        if tag != "br":
            style = (dict(attrs).get("style") or "").replace(" ", "").lower()
            emph = (
                tag in {"b", "strong", "i", "em"}
                or "font-weight:700" in style
                or "font-weight:bold" in style
                or "font-style:italic" in style
            )
            self.stack.append((tag, emph))

    def handle_endtag(self, tag):
        if tag == "ix:header":
            self.hidden -= 1
        for j in range(len(self.stack) - 1, -1, -1):
            if self.stack[j][0] == tag:
                del self.stack[j:]
                break
        if tag in self.BREAK:
            self.flush()

    def handle_data(self, data):
        if not self.hidden:
            self.cur.append((data, any(e for _, e in self.stack)))


def blocks(html: str) -> list[Block]:
    p = _Blocks()
    p.feed(html)
    p.flush()
    return p.blocks


def items(bs: list[Block], wanted: dict[str, str]) -> dict[str, list[Block]]:
    """Body blocks per Item key whose heading matches the title regex in `wanted`.

    A span ends at the next heading of another Item; the longest span wins (skips table-of-contents
    entries); running page headers repeating the same Item are dropped from the body.
    """
    heads = {i: m.group(1).upper() for i, b in enumerate(bs) if (m := ITEM.match(b.text + " "))}
    out = {}
    for key, title in wanted.items():
        spans = [
            (i + 1, next((j for j, k2 in heads.items() if j > i and k2 != key), len(bs)))
            for i, k in heads.items()
            if k == key and re.search(title, bs[i].text, re.I)
        ]
        if spans:
            start, end = max(spans, key=lambda s: s[1] - s[0])
            out[key] = [b for j, b in enumerate(bs[start:end], start) if j not in heads]
    return out


def risk_factors(item_1a: list[Block]) -> list[RiskFactor]:
    """Emphasised sentence-like headings with the text up to the next heading.

    Category headings (no closing period) and headings without body text are dropped;
    repeated consecutive headings are merged.
    """
    out: list[list] = []
    for b in item_1a:
        heading = b.emphasis > 0.9 and 20 < len(b.text) < 600
        if heading and b.text.rstrip().endswith((".", "?")):
            if not (out and out[-1][0] == b.text):
                out.append([b.text, []])
        elif heading:
            continue
        elif out:
            out[-1][1].append(b.text)
    return [RiskFactor(h, " ".join(body)) for h, body in out if body]


def note(item_8: list[Block], title: str) -> list[Block]:
    """Body of the first financial-statement note whose title matches `title` (regex)."""
    heads = [
        i
        for i, b in enumerate(item_8)
        if b.emphasis > 0.9 and len(b.text) < 120 and NOTE.match(b.text)
    ]
    for n, i in enumerate(heads):
        if re.search(title, NOTE.match(item_8[i].text).group(1), re.I):
            return item_8[i + 1 : heads[n + 1] if n + 1 < len(heads) else len(item_8)]
    return []
