"""Command line: `filing-delta ingest` builds data/processed from SEC EDGAR (cached in data/raw)."""

import argparse
import pathlib

import yaml

from filing_delta.edgar import Edgar
from filing_delta.ingest import cross_check, ingest


def main() -> None:
    ap = argparse.ArgumentParser(prog="filing-delta")
    ap.add_argument("command", choices=["ingest"])
    ap.add_argument("--config", default="config/airlines.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(pathlib.Path(args.config).read_text(encoding="utf-8"))
    edgar = Edgar(pathlib.Path("data/raw"))
    summary = ingest(edgar, cfg, pathlib.Path("data/processed"))
    for tk, s in summary.items():
        idx = s["index"]
        forms = [f"{d['form']} {d['filed']}" for d in s["docs"]]
        missing = [
            f"{k} {y}" for k, m in idx["metrics"].items() for y, v in m["values"].items() if not v
        ]
        compared, issues = cross_check(idx, edgar.companyfacts(idx["cik"]))
        print(f"\n{tk}: {', '.join(forms)} · 8-Ks since last 10-K: {len(idx['events'])}")
        for d in s["docs"]:
            sizes = {k: len(v) for k, v in d["sections"].items()}
            rfs = len(d["risk_factors"])
            print(f"  {d['form']} {d['filed']}: sections {sizes} · risk factors {rfs}")
        print(f"  metrics not reported: {missing or 'none'}")
        print(f"  companyfacts cross-check: {compared} compared, mismatches: {issues or 'none'}")
