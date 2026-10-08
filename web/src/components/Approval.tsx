import { useEffect, useState } from "react";
import type { Run, Workspace } from "../types";
import { load } from "../data";
import { render } from "../memo";

type Props = {
  ws: Workspace;
  update: (f: (w: Workspace) => Workspace) => void;
  proposed: string;
  allowed: string[];
  passed: boolean;
  onJump: (pid: string) => void;
};
const STATUSES = ["Stable", "Monitor", "Watchlist"];

/** The analyst's own record: kept Q&A, highlights and notes, and the decision. */
export function MyReview({ ws, update, proposed, allowed, passed, onJump }: Props) {
  const [runs, setRuns] = useState<Record<string, Run>>({});
  const [status, setStatus] = useState(ws.decision?.status ?? proposed);
  const [note, setNote] = useState(ws.decision?.note ?? "");
  useEffect(() => {
    for (const id of ws.kept) if (!runs[id]) load<Run>(`ask-${id}`).then((r) => setRuns((x) => ({ ...x, [id]: r })));
  }, [ws.kept, runs]);
  const override = status !== proposed;
  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-xs font-bold uppercase tracking-wider text-muted">Kept questions ({ws.kept.length})</h3>
        {ws.kept.length === 0 && <p className="mt-2 text-sm text-muted">Keep ☆ answers in Chat to collect them here.</p>}
        <ul className="mt-2 space-y-3">
          {ws.kept.map((id) => {
            const r = runs[id];
            return (
              <li key={id} className="rounded-lg border border-rule p-3 text-sm">
                <p className="font-semibold">{r?.question ?? "…"}</p>
                {r?.refusal && <p className="mt-1 text-muted">{r.refusal}</p>}
                {r?.answer?.map((b, i) => <p key={i} className="mt-1">{render(b.text, r.metrics)}</p>)}
                <button type="button" onClick={() => update((w) => ({ ...w, kept: w.kept.filter((k) => k !== id) }))} className="mt-2 text-xs text-muted underline hover:text-ink">Remove</button>
              </li>
            );
          })}
        </ul>
      </section>
      <section>
        <h3 className="text-xs font-bold uppercase tracking-wider text-muted">Highlights and notes ({ws.highlights.length})</h3>
        {ws.highlights.length === 0 && <p className="mt-2 text-sm text-muted">Select text in the filing to highlight it or add a note.</p>}
        <ul className="mt-2 space-y-2">
          {ws.highlights.map((h) => (
            <li key={h.id}>
              <button type="button" onClick={() => onJump(h.pid)} className={`w-full rounded-lg border-l-4 ${h.color === "red" ? "border-red-400" : "border-yellow-400"} bg-wash p-3 text-left text-sm hover:bg-rule/40`}>
                <span className="block text-xs font-semibold text-muted">{h.color === "red" ? "Concern" : "Important"} · {h.source}</span>
                <span className="mt-1 block">“{h.quote.length > 220 ? `${h.quote.slice(0, 220)}…` : h.quote}”</span>
                {h.note && <span className="mt-1 block font-semibold">✎ {h.note}</span>}
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="rounded-lg border-2 border-ink p-4">
        <h3 className="text-sm font-bold">Decision</h3>
        {ws.decision ? (
          <div className="mt-2 text-sm">
            <p><span className="font-semibold">{ws.decision.status}</span> approved {new Date(ws.decision.at).toLocaleString()}{ws.decision.status !== proposed ? ` (proposed ${proposed})` : ""}</p>
            {ws.decision.note && <p className="mt-1 text-muted">“{ws.decision.note}”</p>}
            <button type="button" onClick={() => update((w) => ({ ...w, decision: null }))} className="mt-2 text-xs underline">Change decision</button>
          </div>
        ) : (
          <>
            <p className="mt-1 text-xs text-muted">Nothing is filed until you approve. Saved in this browser only.</p>
            <div className="mt-3 flex flex-wrap gap-2" role="radiogroup" aria-label="Watch status">
              {STATUSES.map((s) => (
                <label key={s} className={`cursor-pointer rounded-full border px-3 py-1 text-sm ${status === s ? "border-ink bg-ink text-page" : "border-rule"}`}>
                  <input type="radio" name="status" value={s} checked={status === s} onChange={() => setStatus(s)} className="sr-only" />
                  {s}{s === proposed ? " · proposed" : ""}{!allowed.includes(s) ? " · overrides signals" : ""}
                </label>
              ))}
            </div>
            <label htmlFor="decision-note" className="mt-3 block text-xs font-semibold">Note {override && "(required to override)"}</label>
            <textarea id="decision-note" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)}
              className="mt-1 w-full rounded border border-rule p-2 text-sm" placeholder="Reasoning for the credit file" />
            <button type="button" disabled={!passed || (override && !note.trim())}
              onClick={() => update((w) => ({ ...w, decision: { status, note: note.trim(), at: new Date().toISOString() } }))}
              className="mt-2 rounded bg-ink px-4 py-2 text-sm font-semibold text-page disabled:cursor-not-allowed disabled:opacity-40">
              Approve
            </button>
          </>
        )}
      </section>
    </div>
  );
}
