import { useEffect, useMemo, useState } from "react";
import type { Bundle, Detail, Evidence, Index, Metric, Run } from "../types";
import { load } from "../data";
import { useWorkspace } from "../store";
import { buildMemo, download, toMarkdown, type Memo } from "../memo";
import { Brief } from "../components/Brief";
import { Chat } from "./Ask";
import { MyReview } from "../components/Approval";
import { DocReader } from "../components/DocReader";
import { DetailDialog } from "../components/SourcePanel";
import { PrintMemo } from "../components/PrintMemo";
import { StatusChip } from "../components/Status";

type Tab = "brief" | "chat" | "review";

/** One airline: analyst panel (brief, chat, my review) beside the filing reader. */
export function Workspace({ b, index }: { b: Bundle; index: Index }) {
  const run = b.run, d = run.draft!;
  const [ws, update] = useWorkspace(run.ticker);
  const [tab, setTab] = useState<Tab>("brief");
  const [pane, setPane] = useState<"analyst" | "filing">("analyst");
  const [target, setTarget] = useState<{ pid: string; n: number } | null>(null);
  const [detail, setDetail] = useState<{ d: Detail; metrics: Record<string, Metric> } | null>(null);
  const [memo, setMemo] = useState<Memo | null>(null);
  const asks = index.asks.filter((a) => a.ticker === run.ticker);
  const rf = b.documents.rf_map;

  const order = useMemo(() => {
    const ids: string[] = [];
    for (const x of [...d.sections.flatMap((s) => s.bullets), ...d.status_reasons]) for (const c of x.citations) if (run.evidence[c] && !ids.includes(c)) ids.push(c);
    return ids;
  }, [d, run.evidence]);
  const pidOf = (id: string) => rf[id] ?? (id.startsWith("8K-") ? null : id);
  const cited = useMemo(() => new Set(order.map(pidOf).filter((x): x is string => !!x)), [order]);

  const openCite = (id: string, ev: Record<string, Evidence>) => {
    const pid = pidOf(id);
    if (!pid) return window.open(ev[id]?.url, "_blank", "noopener,noreferrer");
    setTarget({ pid, n: Date.now() });
    setPane("filing");
  };
  const keptRuns = () => Promise.all(ws.kept.map((id) => load<Run>(`ask-${id}`)));
  const exportMd = async () => download(`${run.ticker}-FY${run.fiscal_year}-review.md`, toMarkdown(buildMemo(b, await keptRuns(), ws)));
  const print = async () => setMemo(buildMemo(b, await keptRuns(), ws));
  useEffect(() => { if (memo) { window.print(); setMemo(null); } }, [memo]);

  const status = ws.decision?.status ?? d.proposed_status;
  const TABS: [Tab, string][] = [["brief", "Brief"], ["chat", `Chat${ws.chat.length ? ` (${ws.chat.length})` : ""}`], ["review", `My review${ws.kept.length + ws.highlights.length ? ` (${ws.kept.length + ws.highlights.length})` : ""}`]];

  return (
    <>
      <div className="screen-only flex min-h-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-rule px-4 py-2.5">
          <a href="#/" className="text-sm text-muted hover:text-ink">← Airlines</a>
          <label htmlFor="airline" className="sr-only">Airline</label>
          <select id="airline" value={run.ticker} onChange={(e) => (window.location.hash = `#/w/${e.target.value}`)}
            className="rounded border border-rule bg-page px-2 py-1 text-base font-bold">
            {index.coverage.map((c) => <option key={c.ticker} value={c.ticker}>{c.name}</option>)}
          </select>
          <span className="text-sm text-muted">FY{run.fiscal_year}</span>
          <StatusChip status={status} />
          <span className="text-xs text-muted">{ws.decision ? "Approved" : "Proposed · awaiting your decision"}</span>
          <div className="ml-auto flex gap-2">
            <button type="button" onClick={exportMd} className="rounded border border-rule px-3 py-1.5 text-sm font-semibold hover:border-ink">Download .md</button>
            <button type="button" onClick={print} className="rounded bg-ink px-3 py-1.5 text-sm font-semibold text-page">Print</button>
          </div>
        </div>
        <div className="flex border-b border-rule lg:hidden" role="tablist" aria-label="Pane">
          {(["analyst", "filing"] as const).map((p) => (
            <button key={p} type="button" role="tab" aria-selected={pane === p} onClick={() => setPane(p)}
              className={`flex-1 py-2 text-sm font-semibold ${pane === p ? "border-b-2 border-ink" : "text-muted"}`}>
              {p === "analyst" ? "Analyst" : "Filing"}
            </button>
          ))}
        </div>
        <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <section aria-label="Analyst" className={`${pane === "analyst" ? "flex" : "hidden"} min-h-0 flex-col lg:flex`}>
            <div className="flex gap-1 px-4 pt-3" role="tablist" aria-label="Analyst panel">
              {TABS.map(([k, label]) => (
                <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                  className={`rounded-full px-3.5 py-1.5 text-sm ${tab === k ? "bg-ink font-semibold text-page" : "text-muted hover:bg-wash hover:text-ink"}`}>
                  {label}
                </button>
              ))}
            </div>
            <div className={`min-h-0 flex-1 px-4 py-4 ${tab === "chat" ? "flex flex-col" : "overflow-y-auto"}`}>
              {tab === "brief" && (
                <Brief b={b} cite={(c) => (order.indexOf(c) + 1) || null} onCite={(c) => openCite(c, run.evidence)}
                  onDetail={(x) => setDetail({ d: x, metrics: b.metrics })} />
              )}
              {tab === "chat" && (
                <Chat asks={asks} ws={ws} update={update} onCite={(c, r) => openCite(c, r.evidence)}
                  onDetail={(x, r) => setDetail({ d: x, metrics: r.metrics })} />
              )}
              {tab === "review" && (
                <MyReview ws={ws} update={update} proposed={d.proposed_status} allowed={run.allowed_status} passed={run.passed}
                  onJump={(pid) => { setTarget({ pid, n: Date.now() }); setPane("filing"); }} />
              )}
            </div>
          </section>
          <section aria-label="Filing" className={`${pane === "filing" ? "flex" : "hidden"} min-h-0 flex-col border-rule lg:flex lg:border-l`}>
            <DocReader docs={b.documents} changes={b.changes} target={target} cited={cited} highlights={ws.highlights}
              onHighlight={(h) => { const id = crypto.randomUUID(); update((w) => ({ ...w, highlights: [...w.highlights, { ...h, id }] })); return id; }}
              onNote={(id, note) => update((w) => ({ ...w, highlights: w.highlights.map((h) => (h.id === id ? { ...h, note } : h)) }))}
              onRemove={(id) => update((w) => ({ ...w, highlights: w.highlights.filter((h) => h.id !== id) }))} />
          </section>
        </div>
      </div>
      <DetailDialog detail={detail?.d ?? null} metrics={detail?.metrics ?? {}} onDetail={(x) => setDetail((p) => p && { ...p, d: x })} onClose={() => setDetail(null)} />
      {memo && <PrintMemo m={memo} />}
    </>
  );
}
