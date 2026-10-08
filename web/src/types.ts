export type Bullet = { text: string; citations: string[]; metrics: string[]; signals?: string[] };
export type Section = { title: string; bullets: Bullet[] };
export type Metric = {
  label: string; value: number; unit: string; year: number; display: string;
  formula?: string; inputs?: string[];
  source?: { concept: string; fact_id: string; form: string; filed: string; url: string };
};
export type Evidence = { id: string; kind: string; source: string; text: string; url: string; status?: string };
export type Signal = { id: string; level: "red" | "amber" | "green"; text: string; refs: string[] };
export type FilingMeta = { form: string; filed: string; period: string; accession: string; url: string };
export type Attempt = {
  attempt: number; gate_failures: string[];
  evaluator: { bullets?: { n: number; supported: boolean; issue: string }[]; advice_free?: boolean };
};
export type Call = { purpose: string; model: string; tokens_in: number; tokens_out: number; source: string };
export type Draft = { headline: string; sections: Section[]; proposed_status: string; status_reasons: Bullet[] };
export type Run = {
  kind: "review" | "ask"; ticker: string; name: string; fiscal_year: number; passed: boolean;
  filings: { current_10k: FilingMeta; prior_10k: FilingMeta };
  signals: Signal[]; allowed_status: string[]; evidence: Record<string, Evidence>;
  metrics: Record<string, Metric>; trace: Call[]; attempts?: Attempt[];
  draft?: Draft; state?: string;
  question?: string; route?: string; refusal?: string; answer?: Bullet[];
};
export type Change = {
  id: string; status: "added" | "removed" | "modified" | "updated" | "unchanged"; heading: string;
  changed: number; prior_heading?: string; diff?: [string, string][]; body?: string;
};
export type Event = { id: string; filed: string; items: string[]; labels: string[]; url: string };
export type MetricRow = { key: string; label: string; formula?: string; values: Record<string, string | null>; keys: Record<string, string> };
export type Paragraph = { id: string; text: string };
export type DocFiling = {
  accession: string; form: string; filed: string; period: string; url: string;
  sections: { key: string; label: string; paragraphs: Paragraph[] }[];
};
export type Bundle = {
  run: Run; metrics: Record<string, Metric>; metric_rows: MetricRow[];
  maturities: { key: string; label: string; value: number; display: string }[];
  changes: (Change & { paragraph?: string })[]; events: Event[];
  documents: { filings: DocFiling[]; rf_map: Record<string, string> };
};
export type Highlight = {
  id: string; pid: string; start: number; end: number; color: "yellow" | "red"; quote: string; note: string; source: string;
};
export type ChatTurn = { typed: string; askId: string | null };
export type Workspace = {
  chat: ChatTurn[]; kept: string[]; highlights: Highlight[];
  decision: { status: string; note: string; at: string } | null;
};
export type Coverage = {
  ticker: string; name: string; fiscal_year: number; status: string; state: string; headline: string;
  net_leverage: string | null; net_leverage_prior: string | null; interest_coverage: string | null;
  liquid_assets: string | null; changes: Record<string, number>; signals: Record<string, number>;
  current_10k: FilingMeta; events: number;
};
export type Index = { coverage: Coverage[]; asks: { id: string; ticker: string; question: string; route: string }[]; latest_10k: string };
export type Detail = { kind: "metric"; key: string; metric: Metric } | { kind: "signal"; item: Signal };
