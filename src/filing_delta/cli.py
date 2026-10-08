"""Command line: ingest, eval, review, ask, golden, approve."""

import argparse
import json
import os
import pathlib
import sys

import yaml

from filing_delta import evals, export, review
from filing_delta.corpus import load
from filing_delta.edgar import Edgar
from filing_delta.ingest import cross_check, ingest
from filing_delta.llm import LLM
from filing_delta.retrieval import BM25

PROCESSED = pathlib.Path("data/processed")


def _yaml(path: str) -> dict:
    return yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))


def _llm(s: dict, case: str) -> LLM:
    """Client for one case; recording replaces that case's cassette."""
    mode = os.environ.get("RUN_MODE", s["run_mode"])
    cassette = pathlib.Path(s["paths"]["cassettes"]) / f"{case}.jsonl"
    if mode == "record":
        cassette.unlink(missing_ok=True)
    return LLM(mode, cassette, s["models"], s["max_output_tokens"])


def _save(s: dict, name: str, run: dict) -> pathlib.Path:
    path = pathlib.Path(s["paths"]["replays"]) / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=1), encoding="utf-8")
    return path


def _print_review(run: dict) -> None:
    r = run["rendered"]
    print(f"\n{run['name']} — FY{run['fiscal_year']} — {run['state']}\n{r['headline']}")
    for sec in r["sections"]:
        print(f"\n{sec['title']}")
        for b in sec["bullets"]:
            print(f"  • {b['text']}  [{', '.join(b['citations'] + b['metrics'])}]")
    print(f"\nProposed status: {r['proposed_status']}")
    for b in r["status_reasons"]:
        print(f"  • {b['text']}")


def golden(s: dict, only: set[str] = frozenset()) -> bool:
    """Run golden cases (all, or only the named review-TICKER / question ids)."""
    g = _yaml("evals/golden.yaml")
    ok = True
    for tk in g["reviews"]:
        if only and f"review-{tk}" not in only:
            continue
        run = review.annual_review(_llm(s, f"review-{tk}"), s, PROCESSED, tk)
        _save(s, f"review-{tk}", run)
        good = run["passed"] and run["draft"]["proposed_status"] in run["allowed_status"]
        ok &= good
        print(
            f"review {tk}: {'PASS' if good else 'FAIL'} · status {run['draft']['proposed_status']} "
            f"· attempts {len(run['attempts'])} · calls {len(run['trace'])}"
        )
    for q in g["questions"]:
        if only and q["id"] not in only:
            continue
        run = review.ask(_llm(s, f"ask-{q['id']}"), s, PROCESSED, q["ticker"], q["q"])
        _save(s, f"ask-{q['id']}", run)
        good = run["route"] == q["route"] and run["passed"]
        ok &= good
        print(f"ask {q['id']} {q['ticker']}: {'PASS' if good else 'FAIL'} · route {run['route']}")
    return ok


TARGETS = {"hit@5": 0.8, "pair_accuracy": 0.95}  # CI gate: retrieval and risk-factor alignment


def _eval(cfg: dict) -> bool:
    bm25 = BM25(load(PROCESSED, list(cfg["airlines"])))
    r = evals.retrieval(bm25, pathlib.Path("evals/retrieval_gold.yaml"))
    al = evals.alignment(PROCESSED, pathlib.Path("evals/risk_alignment_gold.yaml"))
    print(
        f"retrieval ({r['n']} questions): hit@1 {r['hit@1']:.3f} · hit@5 {r['hit@5']:.3f} "
        f"· MRR {r['mrr']:.3f}"
    )
    print(
        f"risk-factor alignment ({al['pairs']} pairs): accuracy {al['pair_accuracy']:.3f} · "
        f"added/removed P {al['added_removed_precision']:.3f} R {al['added_removed_recall']:.3f}"
    )
    return r["hit@5"] >= TARGETS["hit@5"] and al["pair_accuracy"] >= TARGETS["pair_accuracy"]


def _ingest(cfg: dict) -> None:
    edgar = Edgar(pathlib.Path("data/raw"))
    for tk, res in ingest(edgar, cfg, PROCESSED).items():
        idx = res["index"]
        forms = [f"{d['form']} {d['filed']}" for d in res["docs"]]
        missing = [
            f"{k} {y}" for k, m in idx["metrics"].items() for y, v in m["values"].items() if not v
        ]
        compared, issues = cross_check(idx, edgar.companyfacts(idx["cik"]))
        print(f"\n{tk}: {', '.join(forms)} · 8-Ks since last 10-K: {len(idx['events'])}")
        for d in res["docs"]:
            sizes = {k: len(v) for k, v in d["sections"].items()}
            print(
                f"  {d['form']} {d['filed']}: sections {sizes} · "
                f"risk factors {len(d['risk_factors'])}"
            )
        print(f"  metrics not reported: {missing or 'none'}")
        print(f"  companyfacts cross-check: {compared} compared, mismatches: {issues or 'none'}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="filing-delta")
    ap.add_argument(
        "command", choices=["ingest", "eval", "review", "ask", "golden", "approve", "export"]
    )
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    cfg, s = _yaml("config/airlines.yaml"), _yaml("config/settings.yaml")
    if a.command == "ingest":
        _ingest(cfg)
    elif a.command == "eval":
        sys.exit(0 if _eval(cfg) else 1)
    elif a.command == "review":
        run = review.annual_review(_llm(s, f"review-{a.args[0]}"), s, PROCESSED, a.args[0])
        _print_review(run)
        print(f"\nsaved {_save(s, f'review-{a.args[0]}', run)}")
    elif a.command == "ask":
        run = review.ask(_llm(s, "ask-adhoc"), s, PROCESSED, a.args[0], a.args[1])
        for b in run.get("answer", []):
            print(f"• {b['text']}  [{', '.join(b['citations'] + b['metrics'])}]")
        print(run.get("refusal", ""))
    elif a.command == "export":
        out = pathlib.Path(a.args[0] if a.args else "web/public/data")
        idx = export.export(PROCESSED, pathlib.Path(s["paths"]["replays"]), out, s)
        print(f"exported {len(idx['coverage'])} reviews and {len(idx['asks'])} questions to {out}")
    elif a.command == "golden":
        sys.exit(0 if golden(s, set(a.args)) else 1)
    else:
        tk, status, note = a.args[0], a.args[1], " ".join(a.args[2:])
        run = json.loads((pathlib.Path(s["paths"]["replays"]) / f"review-{tk}.json").read_text())
        entry = review.approve(run, status, note, pathlib.Path(s["paths"]["credit_file"]))
        print(f"credit file updated: {entry}")
