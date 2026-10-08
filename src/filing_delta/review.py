"""Annual review and Ask: code tools → parallel specialists → writer → gates → evaluator."""

import datetime as dt
import json
import pathlib
from concurrent.futures import ThreadPoolExecutor

from filing_delta import gates, tools
from filing_delta.corpus import filings, index, load
from filing_delta.delta import align, word_diff
from filing_delta.injection import redact, wrap
from filing_delta.llm import LLM
from filing_delta.retrieval import BM25

DEBT_QUERIES = [
    "liquidity cash short-term investments undrawn revolving credit facility",
    "covenants minimum liquidity collateral coverage ratio",
    "issued notes term loan repaid debt financing activities",
    "credit rating agency upgrade downgrade investment grade",
]
EVIDENCE_CHARS = 6000  # longest passage is ~5,200 characters; reviewers see it whole
EVENT_QUERIES = [
    "financing activities issued notes term loan repaid",
    "liquidity as of cash undrawn",
]
REFUSALS = {
    "advice": "Filing Delta Agents does not give investment advice or buy, sell or hold views. "
    "Ask about what the filings disclose instead.",
    "forecast": "The filings do not contain that forecast, and this tool does not predict. "
    "Ask about reported figures or management's disclosed plans.",
    "out_of_scope": "That is outside this review. "
    "Ask about this airline's 10-K, 10-Q or 8-K filings.",
}


class Context:
    """Everything code knows about one airline: metrics, risk-factor changes, events, signals."""

    def __init__(self, processed: pathlib.Path, ticker: str, cfg: dict) -> None:
        self.ticker, self.cfg = ticker, cfg
        self.index = index(processed, ticker)
        self.docs = filings(processed, ticker)
        tenks = [d for d in self.docs if d["form"] == "10-K"]
        self.current, self.prior = tenks[0], tenks[1]
        self.year = int(self.current["period"][:4])
        self.metrics = tools.metrics(self.index)
        self.changes = align(self.prior["risk_factors"], self.current["risk_factors"])
        self.events = tools.events(self.index)
        self.signals = tools.signals(
            self.metrics, self.year, self.changes, self.events, cfg["signals"]
        )
        self.allowed = tools.status_allowed(self.signals)
        self.bm25 = BM25([p for p in load(processed, [ticker]) if p.current])
        self.evidence: dict[str, dict] = {}

    def texts(self) -> dict[str, str]:
        return {k: v["text"] for k, v in self.evidence.items()}

    def metric_block(self, years: tuple[int, ...]) -> str:
        rows = [
            f"{k} | {m['label']} | {tools.fmt(m)}"
            for k, m in self.metrics.items()
            if m["year"] in years
        ]
        return "<metrics>\n" + "\n".join(rows) + "\n</metrics>"

    def passage_block(self, queries: list[str], k: int, **where) -> str:
        seen, parts = set(), []
        for q in queries:
            for p, _ in self.bm25.search(q, k=k, **where):
                if p.id in seen:
                    continue
                seen.add(p.id)
                src = f"{p.form} filed {p.filed}, {section_name(p.section)}"
                self.evidence[p.id] = {
                    "id": p.id,
                    "kind": "passage",
                    "source": src,
                    "text": p.text,
                    "url": p.url,
                }
                parts.append(wrap(redact(p.text), src, p.id, p.filed))
        return "<evidence>\n" + "\n".join(parts) + "\n</evidence>"


def section_name(key: str) -> str:
    names = {
        "1A": "Item 1A Risk Factors",
        "7": "Item 7 MD&A",
        "7A": "Item 7A Market Risk",
        "2": "Part I Item 2 MD&A",
        "debt_note": "Debt note",
    }
    return names.get(key, key)


def _prompt(cfg: dict, name: str) -> str:
    root = pathlib.Path(cfg["paths"]["prompts"])
    return (root / "_shared.md").read_text() + "\n" + (root / f"{name}.md").read_text()


def risk_input(ctx: Context) -> str:
    material = [c for c in ctx.changes if c.status in ("added", "removed", "modified")]
    material.sort(key=lambda c: -c.changed)
    lines = []
    for c in material[:8]:
        rf = c.current or c.prior
        when = ctx.current["filed"] if c.current else ctx.prior["filed"]
        src = f"10-K filed {when}, Item 1A risk factor ({c.status})"
        ctx.evidence[rf["id"]] = {
            "id": rf["id"],
            "kind": "risk_factor",
            "source": src,
            "text": f"{rf['heading']} {rf['body']}",
            "status": c.status,
            "url": ctx.current["url"] if c.current else ctx.prior["url"],
        }
        if c.status == "modified":
            ops = word_diff(c.prior["body"], c.current["body"])
            delta = " ".join(f"[{op}: {t}]" for op, t in ops if op != "equal")[:900]
            body = f"Heading: {rf['heading']}\nChanged words: {delta}"
        else:
            body = f"Heading: {rf['heading']}\nText: {rf['body'][:900]}"
        lines.append(wrap(redact(body), src, rf["id"], when))
    counts = {s: sum(c.status == s for c in ctx.changes) for s in ("unchanged", "updated")}
    return f"<changes>\n{chr(10).join(lines)}\n</changes>\n<counts>{json.dumps(counts)}</counts>"


def events_input(ctx: Context) -> str:
    for e in ctx.events:
        ctx.evidence[e["id"]] = {
            "id": e["id"],
            "kind": "event",
            "source": f"8-K filed {e['filed']}",
            "text": "; ".join(e["labels"]),
            "url": e["url"],
        }
    rows = [f"{e['id']} | {e['filed']} | {'; '.join(e['labels'])}" for e in ctx.events]
    ev = "<events>\n" + "\n".join(rows) + "\n</events>"
    return ev + "\n" + ctx.passage_block(EVENT_QUERIES, 3, form="10-Q")


def render(text: str, metrics: dict) -> str:
    return gates.PLACEHOLDER.sub(
        lambda m: tools.fmt(metrics[m.group(1)]) if m.group(1) in metrics else m.group(0), text
    )


def evaluate(llm: LLM, cfg: dict, ctx: Context, bullets: list[dict]) -> dict:
    blocks = []
    for n, b in enumerate(bullets, 1):
        ev = [
            f"[{c}] {ctx.evidence[c]['text'][:EVIDENCE_CHARS]}"
            for c in b["citations"]
            if c in ctx.evidence
        ]
        ms = [f"{k} = {tools.fmt(ctx.metrics[k])}" for k in b["metrics"] if k in ctx.metrics]
        ms += [
            f"{k} = {tools.fmt(ctx.metrics[k])}"
            for k in gates.PLACEHOLDER.findall(b["text"])
            if k in ctx.metrics
        ]
        ev += [
            f"[{x['id']}] code signal ({x['level']}): {x['text']}"
            for x in ctx.signals
            if x["id"] in b["signals"]
        ]
        blocks.append(
            wrap(
                redact(
                    f"{n}. {render(b['text'], ctx.metrics)}\nEvidence: {' | '.join(ev)}\n"
                    f"Metrics: {'; '.join(ms)}"
                ),
                "draft and evidence",
                str(n),
            )
        )
    return llm.json(
        "evaluator",
        _prompt(cfg, "evaluator"),
        "<bullets>\n" + "\n".join(blocks) + "\n</bullets>",
        cfg["temperature"]["evaluator"],
    )


def _norm(b: dict) -> dict:
    """Bullet with list-valued citations, metrics and signals (models sometimes return a string)."""
    out = {"text": str(b.get("text", ""))}
    for k in ("citations", "metrics", "signals"):
        v = b.get(k) or []
        out[k] = [v] if isinstance(v, str) else [str(x) for x in v]
    return out


def _evidence_block(ctx: Context, findings: dict) -> str:
    ids = {c for fs in findings.values() for f in fs for c in (f.get("citations") or [])}
    parts = [
        wrap(redact(ctx.evidence[i]["text"][:EVIDENCE_CHARS]), ctx.evidence[i]["source"], i)
        for i in sorted(ids)
        if i in ctx.evidence
    ]
    return "<evidence>\n" + "\n".join(parts) + "\n</evidence>"


def _verdict_issues(v: dict) -> list[str]:
    out = [
        f"{b['n']}: not supported: {b.get('issue', '')}"
        for b in v.get("bullets", [])
        if not b.get("supported")
    ]
    return out + ([] if v.get("advice_free", True) else ["draft contains investment advice"])


def annual_review(llm: LLM, cfg: dict, processed: pathlib.Path, ticker: str) -> dict:
    ctx = Context(processed, ticker, cfg)
    years = (ctx.year, ctx.year - 1)
    metric_block = ctx.metric_block(years)
    debt_in = metric_block + "\n" + ctx.passage_block(DEBT_QUERIES, 3)
    jobs = {
        "risk_analyst": risk_input(ctx),
        "debt_analyst": debt_in,
        "events_analyst": events_input(ctx),
    }
    t = cfg["temperature"]["specialist"]
    with ThreadPoolExecutor(3) as pool:
        futs = {k: pool.submit(llm.json, k, _prompt(cfg, k), v, t) for k, v in jobs.items()}
        findings = {k: f.result()["findings"] for k, f in futs.items()}
    sig = json.dumps(ctx.signals)
    feedback, attempts = [], []
    for attempt in range(cfg["max_revisions"] + 1):
        user = (
            f"<findings>{json.dumps(findings)}</findings>\n<signals>{sig}</signals>\n"
            f"<allowed_status>{sorted(ctx.allowed)}</allowed_status>\n{metric_block}\n"
            f"{_evidence_block(ctx, findings)}\n<feedback>{json.dumps(feedback)}</feedback>"
        )
        draft = llm.json("writer", _prompt(cfg, "writer"), user, cfg["temperature"]["writer"])
        for s in draft["sections"]:
            s["bullets"] = [_norm(b) for b in s["bullets"]]
        draft["status_reasons"] = [_norm(b) for b in draft["status_reasons"]]
        bullets = [b for s in draft["sections"] for b in s["bullets"]] + draft["status_reasons"]
        gate = gates.check(bullets, ctx.texts(), set(ctx.metrics), {x["id"] for x in ctx.signals})
        gate += gates.status_issue(draft["proposed_status"], ctx.allowed)
        gate += gates.check([{"text": draft["headline"], "citations": ["-"]}], {"-": ""}, set())
        verdict = evaluate(llm, cfg, ctx, bullets) if not gate else {}
        issues = _verdict_issues(verdict) if verdict else []
        attempts.append({"attempt": attempt + 1, "gate_failures": gate, "evaluator": verdict})
        if not gate and not issues:
            break
        feedback = gate + issues
    passed = not gate and not issues
    return _run(
        "review",
        ctx,
        llm,
        {
            "draft": draft,
            "rendered": _render_draft(draft, ctx.metrics),
            "findings": findings,
            "attempts": attempts,
            "passed": passed,
            "state": "AWAITING_APPROVAL" if passed else "NEEDS_ANALYST_REVIEW",
        },
    )


def _render_draft(d: dict, metrics: dict) -> dict:
    def rb(b):
        return {**b, "text": render(b["text"], metrics)}

    return {
        "headline": render(d["headline"], metrics),
        "sections": [
            {"title": s["title"], "bullets": [rb(b) for b in s["bullets"]]} for s in d["sections"]
        ],
        "proposed_status": d["proposed_status"],
        "status_reasons": [rb(b) for b in d["status_reasons"]],
    }


def ask(llm: LLM, cfg: dict, processed: pathlib.Path, ticker: str, question: str) -> dict:
    ctx = Context(processed, ticker, cfg)
    q = wrap(redact(question), "analyst question", "q")
    latest = max(d["filed"] for d in ctx.docs)
    context = (
        f"<context>{ctx.index['name']}. Filings available through {latest}; the latest 10-K covers "
        f"fiscal year {ctx.year}. Anything dated up to then is reported history, not a forecast."
        "</context>"
    )
    route = llm.json(
        "router",
        _prompt(cfg, "router"),
        f"{context}\n<question>{q}</question>",
        cfg["temperature"]["router"],
    )
    if route["route"] != "answer":
        return _run(
            "ask",
            ctx,
            llm,
            {
                "question": question,
                "route": route["route"],
                "refusal": REFUSALS[route["route"]],
                "passed": True,
            },
        )
    metric_block = ctx.metric_block((ctx.year, ctx.year - 1))
    evidence = ctx.passage_block(
        [question, route.get("query") or question], cfg["retrieval_k"] // 2 + 1
    )
    feedback, attempts = [], []
    for attempt in range(cfg["max_revisions"] + 1):
        user = (
            f"<question>{q}</question>\n{metric_block}\n{evidence}\n"
            f"<feedback>{json.dumps(feedback)}</feedback>"
        )
        out = llm.json("answer", _prompt(cfg, "answer"), user, cfg["temperature"]["writer"])
        out["bullets"] = [_norm(b) for b in out["bullets"]]
        gate = gates.check(out["bullets"], ctx.texts(), set(ctx.metrics))
        verdict = evaluate(llm, cfg, ctx, out["bullets"]) if not gate else {}
        issues = _verdict_issues(verdict) if verdict else []
        attempts.append({"attempt": attempt + 1, "gate_failures": gate, "evaluator": verdict})
        if not gate and not issues:
            break
        feedback = gate + issues
    return _run(
        "ask",
        ctx,
        llm,
        {
            "question": question,
            "route": "answer",
            "answer": [{**b, "text": render(b["text"], ctx.metrics)} for b in out["bullets"]],
            "attempts": attempts,
            "passed": not gate and not issues,
        },
    )


def _run(kind: str, ctx: Context, llm: LLM, body: dict) -> dict:
    cited = {c for b in _all_bullets(body) for c in b.get("citations", [])}
    used_metrics = {m for b in _all_bullets(body) for m in b.get("metrics", [])}
    used_metrics |= {
        m for b in _all_bullets(body) for m in gates.PLACEHOLDER.findall(b.get("text", ""))
    }
    return {
        "kind": kind,
        "ticker": ctx.ticker,
        "name": ctx.index["name"],
        "fiscal_year": ctx.year,
        "filings": {"current_10k": _meta(ctx.current), "prior_10k": _meta(ctx.prior)},
        "signals": ctx.signals,
        "allowed_status": sorted(ctx.allowed),
        "evidence": {k: v for k, v in ctx.evidence.items() if k in cited},
        "metrics": {
            k: {**m, "display": tools.fmt(m)}
            for k, m in ctx.metrics.items()
            if k in used_metrics or m["year"] >= ctx.year - 2
        },
        "trace": list(llm.calls),
        **body,
    }


def _all_bullets(body: dict) -> list[dict]:
    d = body.get("draft")
    if d:
        return [b for s in d["sections"] for b in s["bullets"]] + d["status_reasons"]
    return body.get("answer", [])


def _meta(d: dict) -> dict:
    return {k: d[k] for k in ("form", "filed", "period", "accession", "url")}


def approve(run: dict, status: str, note: str, credit_file: pathlib.Path) -> dict:
    """The only writer of the mock credit file: records the analyst's decision on a passed run."""
    if run["kind"] != "review" or not run["passed"]:
        raise ValueError("only a review that passed its gates can be approved")
    if status not in {"Stable", "Monitor", "Watchlist"}:
        raise ValueError(f"unknown status {status!r}")
    entry = {
        "ticker": run["ticker"],
        "fiscal_year": run["fiscal_year"],
        "proposed_status": run["draft"]["proposed_status"],
        "approved_status": status,
        "analyst_note": note,
        "approved_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }
    entries = json.loads(credit_file.read_text()) if credit_file.exists() else []
    credit_file.parent.mkdir(parents=True, exist_ok=True)
    credit_file.write_text(json.dumps(entries + [entry], indent=1))
    return entry
