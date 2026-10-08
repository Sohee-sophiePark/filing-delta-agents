# Filing Delta Agents

**Live replay demo:** https://sohee-sophiepark.github.io/filing-delta-agents/

Every year a credit analyst re-reads a borrower's 10-K to answer one question: *what changed?* New or reworded risk
factors, leverage and interest coverage, near-term maturities, covenants, and the 8-K events since. Filing Delta Agents
does that prep for four US airlines (Delta, United, American, Southwest) and hands the analyst a cited brief with a
proposed internal watch status (Stable, Monitor, Watchlist) to approve or override.

Several tools already diff 10-Ks. The point here is **trust you can check**:

- **Every number comes from code.** Metrics are parsed from the filings' inline XBRL and computed by formula; each value
  opens to its formula, its inputs, and the XBRL concept, fact id and filing it came from. Agents can only refer to
  numbers by key, or quote a figure that code finds verbatim in the passage they cite.
- **Every statement cites its source.** Claims link to the risk factor, MD&A or debt-note passage, or 8-K they rest on.
- **Gates and a separate evaluator.** Code rejects uncited claims, untraceable numbers, advice wording and statuses the
  signals do not allow; an evaluator checks each statement against its evidence and sends drafts back (at most twice).
- **The analyst decides.** Nothing is filed until the analyst approves.
- **Measured.** Retrieval and risk-factor matching are scored against gold sets in CI (results below).

Public SEC data, cited with filing dates. The watch status is illustrative, not a credit rating. Nothing here is
investment advice.

## What the analyst sees

- **Airlines**: one card per airline with proposed status, net leverage (and prior year), interest coverage, cash and
  short-term investments, risk-factor changes and code signals.
- **Workspace** (one per airline): the analyst panel beside the filing itself.
  - **Brief**: key numbers, then *Risk factors*, *Debt and liquidity*, *Events since the 10-K* and the reasons for the
    proposed status. Select a number to see its formula and XBRL source; select a citation to jump to the paragraph.
  - **Chat**: suggested questions and a question box. On the public demo answers are recorded agent runs, and a typed
    question is matched to the closest recorded one (the match is shown). Refusals (advice, forecasts, prompt injection,
    off-topic) are part of the set. Keep the answers you want for the record.
  - **Filing reader**: the latest 10-K and later 10-Qs by section, cited paragraphs marked, and a *changes vs prior year*
    view of the risk factors with inserted and deleted words. Select text to highlight it (important or concern) and add
    a note.
  - **My review**: kept questions, highlights and notes, and the decision (approve or override with a note).
  - **Download .md** and **Print**: a review memo with the decision, brief, key numbers, kept questions, highlights and
    notes, and numbered sources linking to the filings. Work is saved in the browser only.

## Architecture

```
 SEC EDGAR (declared User-Agent, ≤1 request/s, cached)
   submissions · 10-K · 10-Q · 8-K index
        │
 Ingest (code)  inline XBRL facts → per-airline concept map → FY metrics with provenance
                HTML → Items 1A / 7 / 7A, debt note, 10-Q MD&A → paragraphs with ids
                Item 1A → risk factors (headings + bodies)
        │
 Code tools     metrics (EBITDA, leverage, net and lease-adjusted leverage, coverage, liquidity, maturities)
                risk-factor alignment + word diff · 8-K item labels · watch signals · allowed statuses
        │
 Specialists (parallel, read-only, one JSON call each)
   Risk factors │ Debt & liquidity (BM25 passages) │ Events (8-Ks, 10-Q passages)
        │
 Writer (single) → gates (code) ⇄ evaluator (≤2 revisions) → AWAITING_APPROVAL → analyst approves
 Ask: router → refusal template | BM25 passages → answer → same gates and evaluator

 LLM: Gemini free tier over REST, newest-first fallback chain · record/replay cassettes keyed by request hash
```

Design choices:

| Choice | Why |
|---|---|
| Inline XBRL from each filing, not only the companyfacts API | The API drops company-specific and dimensional facts (e.g. United's combined-entity maturities). Values are cross-checked against the API where both exist (182 values, 0 mismatches). |
| Per-airline concept map with the reported label | Airlines tag the same idea differently (Delta reports *interest expense, net*). Missing values stay "not reported", never guessed. |
| Fixed code-run tools + one call per specialist | Fewer calls, deterministic inputs, every number from code. |
| BM25 over passages, scoped to current filings | Meets the retrieval target without embeddings; analyst wording is mapped to filing wording by a small thesaurus. |
| Numbers as `{{m:KEY}}` or verbatim quotes | A gate can verify both; nothing numeric is invented. |
| Filing text wrapped as untrusted data | Embedded instructions are redacted and never followed. |

## Evaluation

Run with `uv run filing-delta eval` and `uv run pytest` (CI runs both, offline).

| Check | Result (2026-10-08) |
|---|---|
| Retrieval: 40 analyst questions, gold passage in top 5 | hit@5 **0.800** · hit@1 0.575 · MRR 0.645 |
| Risk-factor matching: 62 hand-labelled pairs (Delta, American FY2025 vs FY2024) | accuracy **1.000** · added/removed precision 1.000, recall 1.000 |
| Golden runs: 4 annual reviews + 20 questions (4 refusals) | **24/24** pass gates and evaluator; replayed offline in CI |
| XBRL metrics vs SEC companyfacts API | 182 values compared, 0 mismatches |

## Run it

Requires Python 3.11+ with [uv](https://docs.astral.sh/uv/) and Node 22+.

```bash
uv sync
uv run pytest -q                                   # offline: unit tests + golden replays
uv run filing-delta eval                           # retrieval and risk-factor matching scores
uv run filing-delta export web/public/data         # demo data from the recorded runs
npm --prefix web ci && npm --prefix web run dev    # replay UI at http://localhost:5173
```

Live mode (your own keys; free-tier Gemini only):

```bash
cp .env.example .env                               # fill in SEC_USER_AGENT and GEMINI_API_KEY
set -a; . ./.env; set +a
uv run filing-delta ingest                         # fetch and process filings (cached)
RUN_MODE=live uv run filing-delta review DAL       # one annual review
RUN_MODE=live uv run filing-delta ask UAL "Has United drawn on its revolver?"
RUN_MODE=record uv run filing-delta golden         # re-record the golden cases
uv run filing-delta approve DAL Monitor "note"     # the only writer of the mock credit file
```

## Project layout

```
config/      airlines and metric concept map · run settings (models, thresholds)
src/         edgar · ixbrl · sections · ingest · corpus · retrieval · delta · tools · gates · llm · review · export · cli
prompts/     one file per agent role
evals/       retrieval gold · risk-factor alignment gold · golden cases
cassettes/   recorded model responses · replays/ recorded runs · data/processed/ processed filings (public SEC text)
web/         React + Vite static replay UI
```

## Limits

- Signal thresholds are illustrative, not a credit methodology; statuses are not ratings.
- 8-K events are labelled from their item codes; 8-K exhibits are not read.
- Metrics cover what the concept map finds in standard and dimensional XBRL; anything else is shown as not reported.
- The public demo replays recorded runs; it does not call any model or SEC endpoint.

## Data

Filings and XBRL data from [SEC EDGAR](https://www.sec.gov/edgar/search/), a US government source in the public domain,
accessed under the SEC's fair-access guidelines with a declared User-Agent. Each figure and passage cites its filing.

Built with [Claude Code](https://claude.com/claude-code).
