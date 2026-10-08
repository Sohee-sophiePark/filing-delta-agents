import json
import pathlib

import httpx
import pytest
import yaml

from filing_delta import gates, llm, review, tools
from filing_delta.cli import golden

EV = {"p1": "As of December 31, 2025, we had $7.4 billion in liquidity."}
METRICS = {"leverage.2025"}


def issues(text, citations=("p1",), metrics=(), signals=()):
    b = {
        "text": text,
        "citations": list(citations),
        "metrics": list(metrics),
        "signals": list(signals),
    }
    return gates.bullet_issues(b, EV, METRICS, {"S1"})


def test_numbers_must_be_placeholders_or_quoted_from_cited_evidence():
    assert issues("Leverage fell to {{m:leverage.2025}}.") == []
    assert issues("Liquidity was $7.4 billion at year end.") == []
    assert issues("Liquidity was $9.9 billion.")[0].startswith("number 9.9")
    assert issues("Liquidity was $7.4 billion.", citations=())[0] == "no citation, metric or signal"


def test_dates_identifiers_and_aircraft_models_are_not_numbers():
    text = (
        "On June 30, 2026 the PSP3 note and Boeing 737 MAX deliveries were discussed in the 10-Q."
    )
    assert issues(text) == []


def test_advice_unknown_ids_and_signal_support():
    assert "investment-advice wording" in issues("Investors should buy the notes.")
    assert issues("Text.", citations=("nope",)) == ["unknown citation nope"]
    assert issues("Text.", citations=(), metrics=("x.2025",)) == ["unknown metric x.2025"]
    assert issues("Coverage is weak.", citations=(), signals=("S1",)) == []


def test_status_guardrail():
    red = [{"level": "red"}, {"level": "red"}]
    assert tools.status_allowed(red) == {"Monitor", "Watchlist"}
    assert tools.status_allowed([]) == {"Stable", "Monitor"}
    assert gates.status_issue("Stable", {"Monitor"})


def test_metrics_derive_ratios_and_treat_unreported_investments_as_zero():
    index = {
        "filings": [{"accession": "k", "form": "10-K", "filed": "2026-02-01", "url": "u"}],
        "metrics": {
            name: {
                "label": name,
                "values": {"2025": {"value": v, "concept": "c", "fact_id": "f", "accession": "k"}},
            }
            for name, v in {
                "operating_income": 4.0,
                "d_and_a": 2.0,
                "total_debt": 12.0,
                "cash": 3.0,
                "interest_expense": 2.0,
            }.items()
        }
        | {"short_term_investments": {"label": "sti", "values": {"2025": None}}},
    }
    m = tools.metrics(index)
    assert m["ebitda.2025"]["value"] == 6.0
    assert m["net_leverage.2025"]["value"] == 1.5
    assert m["interest_coverage.2025"]["value"] == 2.0
    assert tools.fmt({"value": 1.5, "unit": "x"}) == "1.5x"


def _client(responses):
    def handler(request):
        status, body = responses.pop(0)
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def ok(text):
    return 200, {"candidates": [{"content": {"parts": [{"text": text}]}}], "usageMetadata": {}}


def test_live_falls_back_on_quota_and_invalid_json_then_records(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    http = _client([(429, {}), ok("not json"), ok('{"a": 1}')])
    cassette = tmp_path / "c.jsonl"
    client = llm.LLM("record", cassette, ["m1", "m2", "m3"], 100, http)
    assert client.json("p", "sys", "user", 0.0) == {"a": 1}
    assert client.calls[-1]["model"] == "m3"
    replay = llm.LLM("replay", cassette, ["m1"], 100)
    assert replay.json("p", "sys", "user", 0.0) == {"a": 1}
    with pytest.raises(llm.CassetteMiss):
        replay.json("p", "sys", "other", 0.0)


def test_approve_is_the_only_writer_and_needs_a_passed_review(tmp_path):
    credit = tmp_path / "credit.json"
    run = {
        "kind": "review",
        "passed": False,
        "ticker": "DAL",
        "fiscal_year": 2025,
        "draft": {"proposed_status": "Monitor"},
    }
    with pytest.raises(ValueError):
        review.approve(run, "Monitor", "note", credit)
    assert not credit.exists()
    review.approve({**run, "passed": True}, "Watchlist", "analyst override", credit)
    assert json.loads(credit.read_text())[0]["approved_status"] == "Watchlist"


def test_golden_cases_replay_offline(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("RUN_MODE", "replay")
    s = yaml.safe_load(pathlib.Path("config/settings.yaml").read_text())
    s["paths"]["replays"] = str(tmp_path)
    assert golden(s)
