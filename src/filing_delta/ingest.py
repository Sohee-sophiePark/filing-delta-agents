"""Per-airline corpus: filings, sections with paragraph ids, risk factors, XBRL metrics."""

import json
import pathlib
from dataclasses import asdict

from filing_delta import ixbrl, sections
from filing_delta.edgar import ARCHIVE, Edgar

MDNA = r"management|md&a"
TENK_ITEMS = {"1A": "risk", "7": MDNA, "7A": "market risk", "8": "financial", "8A": "financial"}
TENQ_ITEMS = {"1A": "risk", "2": MDNA}


def select(sub: dict, annual: int) -> list[dict]:
    """Latest `annual` 10-Ks, plus the 10-Qs and 8-Ks filed after the newest 10-K, newest first."""
    r = sub["filings"]["recent"]
    rows = [
        {
            "form": r["form"][i],
            "filed": r["filingDate"][i],
            "period": r["reportDate"][i],
            "accession": r["accessionNumber"][i],
            "doc": r["primaryDocument"][i],
            "items": r["items"][i],
        }
        for i in range(len(r["form"]))
    ]
    rows.sort(key=lambda x: x["filed"], reverse=True)
    tenks = [x for x in rows if x["form"] == "10-K"][:annual]
    since = tenks[0]["filed"]
    return tenks + [x for x in rows if x["form"] in ("10-Q", "8-K") and x["filed"] > since]


def paragraphs(acc: str, key: str, bs: list[sections.Block]) -> list[dict]:
    return [{"id": f"{acc}#{key}-{n}", "text": b.text} for n, b in enumerate(bs)]


def process(meta: dict, html: str, debt_title: str) -> dict:
    """One 10-K or 10-Q → sections, risk factors, debt note (10-K) and numeric facts."""
    bs = sections.blocks(html)
    its = sections.items(bs, TENK_ITEMS if meta["form"] == "10-K" else TENQ_ITEMS)
    acc = meta["accession"]
    out = {**meta, "sections": {k: paragraphs(acc, k, v) for k, v in its.items() if k[0] != "8"}}
    out["risk_factors"] = [
        {"id": f"{acc}#RF-{n}", **asdict(rf)}
        for n, rf in enumerate(sections.risk_factors(its.get("1A", [])))
    ]
    if meta["form"] == "10-K":
        note = sections.note(its.get("8") or its.get("8A") or [], debt_title)
        out["sections"]["debt_note"] = paragraphs(acc, "debt", note)
    out["facts"] = [asdict(f) for f in ixbrl.facts(html)]
    return out


def spec(cfg: dict, ticker: str) -> dict[str, dict]:
    over = cfg.get("overrides", {}).get(ticker, {})
    return {k: {**v, **over.get(k, {})} for k, v in cfg["metrics"].items()}


def _match(f: dict, s: dict, concept: str, year: int) -> bool:
    name = concept if ":" in concept else f"us-gaap:{concept}"
    dims = sorted((s.get("dims") or {}).items())
    end_ok = f["end"] == f"{year}-12-31"
    period_ok = f["start"] == f"{year}-01-01" if s["period"] == "duration" else f["start"] is None
    return f["concept"] == name and [tuple(d) for d in f["dims"]] == dims and end_ok and period_ok


def metrics(cfg: dict, ticker: str, tenks: list[dict]) -> dict:
    """Fiscal-year metric values with provenance; newest 10-K first, None when not reported."""
    years = sorted({int(t["period"][:4]) for t in tenks})
    out = {}
    for key, s in spec(cfg, ticker).items():
        values = {}
        for y in years:
            hit = next(
                (
                    (t, f)
                    for t in tenks
                    for c in s["concepts"]
                    for f in t["facts"]
                    if _match(f, s, c, y)
                ),
                None,
            )
            if hit:
                t, f = hit
                values[y] = {
                    "value": -f["value"] if s.get("negate") else f["value"],
                    "concept": f["concept"],
                    "fact_id": f["fact_id"],
                    "accession": t["accession"],
                    "filed": t["filed"],
                }
            else:
                values[y] = None
        out[key] = {"label": s["label"], "values": values}
    return out


def ingest(edgar: Edgar, cfg: dict, out_dir: pathlib.Path) -> dict[str, dict]:
    """Fetch (cached) and process every airline; writes one JSON per filing plus index.json."""
    summary = {}
    for tk, a in cfg["airlines"].items():
        cik = a["cik"]
        chosen = select(edgar.submissions(cik), cfg["annual_filings"])
        docs = []
        for meta in [m for m in chosen if m["form"] in ("10-K", "10-Q")]:
            meta["url"] = ARCHIVE.format(
                cik=cik, acc=meta["accession"].replace("-", ""), doc=meta["doc"]
            )
            html = edgar.document(cik, meta["accession"], meta["doc"]).decode("utf-8", "replace")
            docs.append(process(meta, html, cfg["debt_note_title"]))
        d = out_dir / tk
        d.mkdir(parents=True, exist_ok=True)
        for doc in docs:
            slim = {k: v for k, v in doc.items() if k != "facts"}  # facts feed metrics() only
            (d / f"{doc['accession']}.json").write_text(json.dumps(slim), encoding="utf-8")
        index = {
            "ticker": tk,
            "name": a["name"],
            "cik": cik,
            "filings": [
                {k: v for k, v in x.items() if k != "items"} for x in chosen if x["form"] != "8-K"
            ],
            "events": [x for x in chosen if x["form"] == "8-K"],
            "metrics": metrics(cfg, tk, [x for x in docs if x["form"] == "10-K"]),
        }
        (d / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
        summary[tk] = {"docs": docs, "index": index}
    return summary


def cross_check(index: dict, companyfacts: dict) -> tuple[int, list[str]]:
    """(values compared, mismatches) between resolved metrics and the SEC companyfacts API."""
    issues, compared = [], 0
    for key, m in index["metrics"].items():
        for year, v in m["values"].items():
            if not v:
                continue
            units = companyfacts["facts"].get("us-gaap", {}).get(v["concept"].split(":")[1], {})
            same = [
                f["val"]
                for f in units.get("units", {}).get("USD", [])
                if f.get("accn") == v["accession"] and f["end"] == f"{year}-12-31"
            ]
            raw = abs(v["value"])
            compared += bool(same)
            if same and not any(abs(abs(x) - raw) < 0.5 for x in same):
                issues.append(f"{key} {year}: parsed {raw:,.0f} vs API {same}")
    return compared, issues
