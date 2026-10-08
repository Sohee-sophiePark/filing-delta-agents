"""Static demo data: recorded runs plus the code-computed context the UI shows next to them."""

import json
import pathlib

import yaml

from filing_delta import tools
from filing_delta.delta import word_diff
from filing_delta.review import Context

KEY_METRICS = [
    "revenue",
    "ebitda",
    "ebitda_margin",
    "total_debt",
    "liquid_assets",
    "net_debt",
    "leverage",
    "net_leverage",
    "lease_adjusted_leverage",
    "interest_coverage",
    "cfo_to_debt",
]
MATURITIES = [
    "maturity_y1",
    "maturity_y2",
    "maturity_y3",
    "maturity_y4",
    "maturity_y5",
    "maturity_after_y5",
]


def _metric_rows(ctx: Context) -> list[dict]:
    years = [ctx.year - 2, ctx.year - 1, ctx.year]
    rows = []
    for name in KEY_METRICS:
        cells = {y: ctx.metrics.get(f"{name}.{y}") for y in years}
        first = next((m for m in cells.values() if m), None)
        if first:
            rows.append(
                {
                    "key": name,
                    "label": first["label"],
                    "formula": first.get("formula"),
                    "values": {str(y): (tools.fmt(m) if m else None) for y, m in cells.items()},
                    "keys": {str(y): f"{name}.{y}" for y in years},
                }
            )
    return rows


SECTION_LABELS = {
    "1A": "Risk factors",
    "7": "MD&A",
    "2": "MD&A",
    "7A": "Market risk",
    "debt_note": "Debt note",
}


def _heading_paragraph(rf: dict, paragraphs: list[dict]) -> str | None:
    """Id of the Item 1A paragraph that starts this risk factor (headings may wrap two blocks)."""
    h = rf["heading"]
    return next(
        (
            p["id"]
            for p in paragraphs
            if p["text"] == h or (len(p["text"]) > 20 and h.startswith(p["text"]))
        ),
        None,
    )


def _documents(ctx: Context) -> dict:
    """Readable text of the latest 10-K and later 10-Qs, plus risk-factor id → paragraph id."""
    docs = [ctx.current] + [
        d for d in ctx.docs if d["form"] == "10-Q" and d["filed"] > ctx.current["filed"]
    ]
    filings = [
        {
            **{k: d[k] for k in ("accession", "form", "filed", "period", "url")},
            "sections": [
                {"key": k, "label": SECTION_LABELS.get(k, k), "paragraphs": v}
                for k, v in d["sections"].items()
                if v and k in SECTION_LABELS
            ],
        }
        for d in docs
    ]
    paras = ctx.current["sections"].get("1A", [])
    rf_map = {
        rf["id"]: pid
        for rf in ctx.current["risk_factors"]
        if (pid := _heading_paragraph(rf, paras))
    }
    return {"filings": filings, "rf_map": rf_map}


def _changes(ctx: Context) -> list[dict]:
    out = []
    paras = ctx.current["sections"].get("1A", [])
    for c in ctx.changes:
        rf = c.current or c.prior
        item = {"id": rf["id"], "status": c.status, "heading": rf["heading"], "changed": c.changed}
        if c.current:
            item["paragraph"] = _heading_paragraph(c.current, paras)
        if c.status in ("modified", "updated"):
            item["prior_heading"] = c.prior["heading"]
            item["diff"] = word_diff(c.prior["body"], c.current["body"])
        elif c.status in ("added", "removed"):
            item["body"] = rf["body"]
        out.append(item)
    order = {"added": 0, "removed": 1, "modified": 2, "updated": 3, "unchanged": 4}
    return sorted(out, key=lambda x: (order[x["status"]], -x["changed"]))


def export(processed: pathlib.Path, replays: pathlib.Path, out: pathlib.Path, s: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    golden = yaml.safe_load(pathlib.Path("evals/golden.yaml").read_text())
    coverage = []
    for tk in golden["reviews"]:
        run = json.loads((replays / f"review-{tk}.json").read_text())
        ctx = Context(processed, tk, s)
        metrics = {k: {**m, "display": tools.fmt(m)} for k, m in ctx.metrics.items()}
        bundle = {
            "run": run,
            "metrics": metrics,
            "metric_rows": _metric_rows(ctx),
            "maturities": [
                {
                    "key": f"{k}.{ctx.year}",
                    "label": metrics[f"{k}.{ctx.year}"]["label"],
                    "value": metrics[f"{k}.{ctx.year}"]["value"],
                    "display": metrics[f"{k}.{ctx.year}"]["display"],
                }
                for k in MATURITIES
                if f"{k}.{ctx.year}" in metrics
            ],
            "changes": _changes(ctx),
            "events": ctx.events,
            "documents": _documents(ctx),
        }
        (out / f"{tk}.json").write_text(json.dumps(bundle), encoding="utf-8")
        counts = {
            st: sum(c.status == st for c in ctx.changes)
            for st in ("added", "removed", "modified", "updated", "unchanged")
        }
        y = ctx.year

        def show(k, metrics=metrics):
            return metrics[k]["display"] if k in metrics else None

        coverage.append(
            {
                "ticker": tk,
                "name": run["name"],
                "fiscal_year": y,
                "status": run["draft"]["proposed_status"],
                "state": run["state"],
                "headline": run["rendered"]["headline"],
                "net_leverage": show(f"net_leverage.{y}"),
                "net_leverage_prior": show(f"net_leverage.{y - 1}"),
                "interest_coverage": show(f"interest_coverage.{y}"),
                "liquid_assets": show(f"liquid_assets.{y}"),
                "changes": counts,
                "signals": {
                    lv: sum(x["level"] == lv for x in run["signals"])
                    for lv in ("red", "amber", "green")
                },
                "current_10k": run["filings"]["current_10k"],
                "events": len(ctx.events),
            }
        )
    asks = []
    for q in golden["questions"]:
        run = json.loads((replays / f"ask-{q['id']}.json").read_text())
        (out / f"ask-{q['id']}.json").write_text(json.dumps(run), encoding="utf-8")
        asks.append(
            {"id": q["id"], "ticker": q["ticker"], "question": q["q"], "route": run["route"]}
        )
    latest = max(c["current_10k"]["filed"] for c in coverage)
    index = {"coverage": coverage, "asks": asks, "latest_10k": latest}
    (out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return index
