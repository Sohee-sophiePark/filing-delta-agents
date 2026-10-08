import type { Bullet, Bundle, Evidence, Metric, Run, Workspace } from "./types";

const PLACEHOLDER = /\{\{m:([a-z0-9_.]+)\}\}/g;
export const render = (t: string, m: Record<string, Metric>) => t.replace(PLACEHOLDER, (x, k) => m[k]?.display ?? x);

type Item = { text: string; refs: number[] };
export type Memo = {
  title: string; meta: string[];
  headline: string; sections: { title: string; items: Item[] }[];
  numbers: { label: string; values: (string | null)[] }[]; years: string[];
  kept: { question: string; items: Item[]; refusal?: string }[];
  highlights: { quote: string; kind: string; note: string; source: string }[];
  sources: { n: number; label: string; url: string }[];
};

/** Everything the analyst keeps for the record: brief, decision, kept Q&A, highlights, numbers, sources. */
export function buildMemo(b: Bundle, kept: Run[], ws: Workspace): Memo {
  const run = b.run, d = run.draft!;
  const sources: Memo["sources"] = [];
  const seen = new Map<string, number>();
  const ref = (id: string, ev: Record<string, Evidence>) => {
    const e = ev[id];
    if (!e) return null;
    if (!seen.has(id)) {
      sources.push({ n: sources.length + 1, label: e.source, url: e.url });
      seen.set(id, sources.length);
    }
    return seen.get(id)!;
  };
  const item = (x: Bullet, ev: Record<string, Evidence>, m: Record<string, Metric>): Item => ({
    text: render(x.text, m),
    refs: x.citations.map((c) => ref(c, ev)).filter((n): n is number => n !== null),
  });
  const years = Object.keys(b.metric_rows[0]?.values ?? {});
  const dec = ws.decision;
  return {
    title: `${run.name}: FY${run.fiscal_year} annual credit review`,
    meta: [
      `Current 10-K filed ${run.filings.current_10k.filed}; prior 10-K filed ${run.filings.prior_10k.filed}.`,
      `Proposed status: ${d.proposed_status}. Decision: ${dec ? `${dec.status} (approved ${dec.at.slice(0, 10)})${dec.note ? `. Note: ${dec.note}` : ""}` : "not yet approved"}.`,
      "Public SEC filings. Watch status is illustrative, not a credit rating. Not investment advice.",
    ],
    headline: render(d.headline, b.metrics),
    sections: [
      ...d.sections.map((s) => ({ title: s.title, items: s.bullets.map((x) => item(x, run.evidence, b.metrics)) })),
      { title: `Why ${d.proposed_status}`, items: d.status_reasons.map((x) => item(x, run.evidence, b.metrics)) },
    ],
    years,
    numbers: b.metric_rows.map((r) => ({ label: r.label, values: years.map((y) => r.values[y]) })),
    kept: kept.map((k) => ({
      question: k.question ?? "",
      refusal: k.refusal,
      items: (k.answer ?? []).map((x) => item(x, k.evidence, k.metrics)),
    })),
    highlights: ws.highlights.map((h) => ({ quote: h.quote, kind: h.color === "red" ? "Concern" : "Important", note: h.note, source: h.source })),
    sources,
  };
}

export function toMarkdown(m: Memo): string {
  const refs = (r: number[]) => (r.length ? " " + r.map((n) => `[${n}]`).join("") : "");
  const out = [`# ${m.title}`, "", ...m.meta.map((x) => `_${x}_`), "", `**${m.headline}**`, ""];
  for (const s of m.sections) out.push(`## ${s.title}`, "", ...s.items.map((i) => `- ${i.text}${refs(i.refs)}`), "");
  out.push("## Key numbers", "", `| Metric | ${m.years.map((y) => `FY${y}`).join(" | ")} |`, `|---|${m.years.map(() => "---:").join("|")}|`);
  out.push(...m.numbers.map((r) => `| ${r.label} | ${r.values.map((v) => v ?? "—").join(" | ")} |`), "");
  if (m.kept.length) {
    out.push("## Kept questions", "");
    for (const k of m.kept) out.push(`**Q: ${k.question}**`, "", ...(k.refusal ? [k.refusal] : k.items.map((i) => `- ${i.text}${refs(i.refs)}`)), "");
  }
  if (m.highlights.length) {
    out.push("## Highlights and notes", "");
    for (const h of m.highlights) out.push(`- **${h.kind}**: “${h.quote}” (${h.source})${h.note ? `\n  - Note: ${h.note}` : ""}`);
    out.push("");
  }
  out.push("## Sources", "", ...m.sources.map((s) => `${s.n}. ${s.label}: ${s.url}`), "");
  return out.join("\n");
}

export function download(name: string, text: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}
