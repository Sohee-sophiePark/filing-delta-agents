"""Numeric inline-XBRL facts from a filing's HTML, with period and dimensions."""

from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass(frozen=True)
class Fact:
    concept: str
    value: float
    start: str | None  # None for instant facts
    end: str
    dims: tuple[tuple[str, str], ...]
    unit: str
    fact_id: str


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.contexts: dict[str, dict] = {}
        self.raw: list[tuple[dict, str]] = []
        self._ctx: dict | None = None
        self._field: str | None = None
        self._fact: dict | None = None
        self._depth = 0
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "xbrli:context":
            self._ctx = {"id": a["id"], "start": None, "end": None, "dims": []}
        elif self._ctx is not None and tag in {"xbrli:startdate", "xbrli:enddate", "xbrli:instant"}:
            self._field, self._text = tag, []
        elif self._ctx is not None and tag == "xbrldi:explicitmember":
            self._field, self._text, self._dim = tag, [], a.get("dimension", "")
        elif tag == "ix:nonfraction":
            if self._fact is None:
                self._fact, self._depth, self._text = a, 0, []
            else:
                self._depth += 1

    def handle_endtag(self, tag):
        if self._field and tag == self._field:
            text = "".join(self._text).strip()
            if tag == "xbrli:startdate":
                self._ctx["start"] = text
            elif tag == "xbrldi:explicitmember":
                self._ctx["dims"].append((self._dim, text))
            else:
                self._ctx["end"] = text
            self._field = None
        elif tag == "xbrli:context" and self._ctx is not None:
            self.contexts[self._ctx["id"]] = self._ctx
            self._ctx = None
        elif tag == "ix:nonfraction" and self._fact is not None:
            if self._depth:
                self._depth -= 1
            else:
                self.raw.append((self._fact, "".join(self._text)))
                self._fact = None

    def handle_data(self, data):
        if self._field or self._fact is not None:
            self._text.append(data)


def _value(attrs: dict, text: str) -> float | None:
    fmt = attrs.get("format", "")
    if fmt.endswith("fixed-zero") or text.strip() in {"", "-", "—", "–"}:
        number = 0.0
    elif fmt and not fmt.endswith(("num-dot-decimal", "numdotdecimal")):
        return None
    else:
        number = float(text.replace(",", "").replace(" ", ""))
    number *= 10 ** int(attrs.get("scale", "0"))
    return -number if attrs.get("sign") == "-" else number


def facts(html: str) -> list[Fact]:
    """All numeric facts; non-numeric formats (e.g. number words) are skipped."""
    p = _Parser()
    p.feed(html)
    out = []
    for attrs, text in p.raw:
        ctx = p.contexts.get(attrs.get("contextref", ""))
        value = _value(attrs, text) if ctx and attrs.get("xsi:nil") != "true" else None
        if value is not None:
            out.append(
                Fact(
                    attrs["name"],
                    value,
                    ctx["start"],
                    ctx["end"],
                    tuple(sorted(ctx["dims"])),
                    attrs.get("unitref", ""),
                    attrs.get("id", ""),
                )
            )
    return out
