"""Deterministic credit tools: metrics with provenance, maturity wall, 8-K events, watch signals."""

import re

ITEMS_8K = {
    "1.01": "Entry into a material definitive agreement",
    "1.02": "Termination of a material definitive agreement",
    "2.02": "Results of operations and financial condition",
    "2.03": "Creation of a direct financial obligation",
    "2.04": "Triggering events that accelerate a financial obligation",
    "2.05": "Exit or disposal costs",
    "2.06": "Material impairments",
    "3.01": "Delisting notice",
    "4.02": "Non-reliance on previously issued financial statements",
    "5.02": "Departure or appointment of directors or officers",
    "5.03": "Amendments to articles or bylaws",
    "5.07": "Shareholder vote results",
    "7.01": "Regulation FD disclosure",
    "8.01": "Other events",
    "9.01": "Financial statements and exhibits",
}
DERIVED = {  # key: (label, unit, formula over same-year inputs)
    "ebitda": ("EBITDA (operating income + D&A)", "usd", "operating_income + d_and_a"),
    "liquid_assets": ("Cash and short-term investments", "usd", "cash + short_term_investments"),
    "net_debt": ("Net debt", "usd", "total_debt - liquid_assets"),
    "lease_adjusted_debt": (
        "Lease-adjusted debt",
        "usd",
        "total_debt + operating_lease_liability + finance_lease_liability",
    ),
    "leverage": ("Debt / EBITDA", "x", "total_debt / ebitda"),
    "net_leverage": ("Net debt / EBITDA", "x", "net_debt / ebitda"),
    "lease_adjusted_leverage": (
        "Lease-adjusted debt / EBITDA",
        "x",
        "lease_adjusted_debt / ebitda",
    ),
    "interest_coverage": (
        "Operating income / interest expense",
        "x",
        "operating_income / interest_expense",
    ),
    "ebitda_margin": ("EBITDA margin", "pct", "ebitda / revenue"),
    "cfo_to_debt": ("Operating cash flow / debt", "pct", "cfo / total_debt"),
}
UNITS = {"usd": "usd"}


def _eval(formula: str, env: dict[str, float]) -> float | None:
    names = re.findall(r"[a-z_]+", formula)
    vals = {n: env.get(n) for n in names}
    if "short_term_investments" in vals and vals["short_term_investments"] is None:
        vals["short_term_investments"] = 0.0  # not reported on the balance sheet
    if any(v is None for v in vals.values()):
        return None
    result = eval(formula, {"__builtins__": {}}, vals)  # formulas are the fixed strings above
    return None if isinstance(result, float) and result != result else result


def metrics(index: dict) -> dict[str, dict]:
    """Metric registry keyed `name.year`: value, unit, label, formula or XBRL source."""
    out: dict[str, dict] = {}
    years = sorted({int(y) for m in index["metrics"].values() for y in m["values"]})
    filings = {f["accession"]: f for f in index["filings"]}
    for y in years:
        env = {}
        for name, m in index["metrics"].items():
            v = m["values"].get(str(y)) or m["values"].get(y)
            env[name] = v["value"] if v else None
            if v:
                f = filings[v["accession"]]
                out[f"{name}.{y}"] = {
                    "label": m["label"],
                    "value": v["value"],
                    "unit": "usd",
                    "year": y,
                    "source": {
                        "concept": v["concept"],
                        "fact_id": v["fact_id"],
                        "form": f["form"],
                        "filed": f["filed"],
                        "url": f.get("url", ""),
                    },
                }
        for name, (label, unit, formula) in DERIVED.items():
            try:
                value = _eval(formula, env)
            except ZeroDivisionError:
                value = None
            env[name] = value
            if value is not None:
                inputs = [f"{n}.{y}" for n in re.findall(r"[a-z_]+", formula) if f"{n}.{y}" in out]
                out[f"{name}.{y}"] = {
                    "label": label,
                    "value": value,
                    "unit": unit,
                    "year": y,
                    "formula": formula,
                    "inputs": inputs,
                }
    return out


def fmt(m: dict) -> str:
    v = m["value"]
    if m["unit"] == "x":
        return f"{v:.1f}x"
    if m["unit"] == "pct":
        return f"{v * 100:.1f}%"
    return f"${v / 1e9:,.1f}bn" if abs(v) >= 1e9 else f"${v / 1e6:,.0f}m"


def events(index: dict) -> list[dict]:
    """8-K filings since the latest 10-K, labelled from their item codes."""
    out = []
    for e in index["events"]:
        items = [i for i in e["items"].split(",") if i]
        out.append(
            {
                "id": f"8K-{e['accession']}",
                "filed": e["filed"],
                "items": items,
                "labels": [ITEMS_8K.get(i, f"Item {i}") for i in items],
                "url": f"https://www.sec.gov/Archives/edgar/data/{index['cik']}/"
                f"{e['accession'].replace('-', '')}/{e['doc']}",
            }
        )
    return out


def signals(ms: dict, year: int, changes: list, evs: list[dict], cfg: dict) -> list[dict]:
    """Watch signals (red | amber | green) from metrics, risk-factor changes and 8-K items."""
    s, out = cfg, []

    def val(k):
        return ms.get(k, {}).get("value")

    def add(level, text, refs):
        out.append({"id": f"S{len(out) + 1}", "level": level, "text": text, "refs": refs})

    nl = val(f"net_leverage.{year}")
    if nl is not None and nl > s["net_leverage_high"]:
        add("red", "Net leverage above the illustrative threshold", [f"net_leverage.{year}"])
    lv, lv0 = val(f"leverage.{year}"), val(f"leverage.{year - 1}")
    if lv is not None and lv0 is not None:
        refs = [f"leverage.{year}", f"leverage.{year - 1}"]
        if lv - lv0 > s["leverage_change"]:
            add("red", "Leverage rose year over year", refs)
        elif lv0 - lv > s["leverage_change"]:
            add("green", "Leverage fell year over year", refs)
    cov = val(f"interest_coverage.{year}")
    if cov is not None and cov < s["coverage_low"]:
        add(
            "red",
            "Interest coverage below the illustrative threshold",
            [f"interest_coverage.{year}"],
        )
    two = sum(val(f"maturity_y{i}.{year}") or 0 for i in (1, 2))
    cash = val(f"liquid_assets.{year}")
    if cash and two / cash > s["maturities_vs_cash"]:
        refs = [f"maturity_y1.{year}", f"maturity_y2.{year}", f"liquid_assets.{year}"]
        add("amber", "Next two years of debt maturities are large relative to cash", refs)
    for c in changes:
        rf = c.current or c.prior
        if c.status in ("added", "removed") and re.search(s["credit_terms"], rf["heading"], re.I):
            add("amber", f"Credit-related risk factor {c.status}", [rf["id"]])
    for e in evs:
        if set(e["items"]) & set(s["credit_8k_items"]):
            add("amber", "Credit-relevant 8-K since the 10-K", [e["id"]])
    return out


def status_allowed(sigs: list[dict]) -> set[str]:
    """Statuses consistent with signals: 2+ red rules out Stable; none rules out Watchlist."""
    red = sum(x["level"] == "red" for x in sigs)
    amber = sum(x["level"] == "amber" for x in sigs)
    allowed = {"Stable", "Monitor", "Watchlist"}
    if red >= 2:
        allowed.discard("Stable")
    if red == 0 and amber == 0:
        allowed.discard("Watchlist")
    return allowed
