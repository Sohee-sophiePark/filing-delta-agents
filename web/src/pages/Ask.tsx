import { useEffect, useRef, useState } from "react";
import type { Detail, Run, Workspace } from "../types";
import { load } from "../data";
import { closest } from "../match";
import { BulletText } from "../components/RichText";

type Q = { id: string; ticker: string; question: string; route: string };
type Props = {
  asks: Q[];
  ws: Workspace;
  update: (f: (w: Workspace) => Workspace) => void;
  onCite: (id: string, run: Run) => void;
  onDetail: (d: Detail, run: Run) => void;
};
const ROUTE: Record<string, string> = { advice: "Refused: investment advice", forecast: "Refused: forecast", out_of_scope: "Refused: out of scope" };

/** Chat over recorded answers: suggestions, closest-match for typed questions, Keep to save a Q&A pair. */
export function Chat({ asks, ws, update, onCite, onDetail }: Props) {
  const [runs, setRuns] = useState<Record<string, Run>>({});
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    for (const t of ws.chat) if (t.askId && !runs[t.askId]) load<Run>(`ask-${t.askId}`).then((r) => setRuns((x) => ({ ...x, [t.askId!]: r })));
  }, [ws.chat, runs]);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [ws.chat.length, Object.keys(runs).length]);
  const ask = (typed: string, id?: string) => {
    const hit = id ? asks.find((a) => a.id === id) : closest(typed, asks);
    update((w) => ({ ...w, chat: [...w.chat, { typed, askId: hit?.id ?? null }] }));
  };
  const asked = new Set(ws.chat.map((t) => t.askId));
  const suggestions = asks.filter((a) => !asked.has(a.id));
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto pb-4">
        {ws.chat.length === 0 && (
          <p className="rounded-lg bg-wash p-4 text-sm text-muted">
            Ask about this airline's filings. Answers here are recorded agent runs: a typed question is matched to the closest
            recorded one, and the match is shown. Keep ☆ the answers you want in your review.
          </p>
        )}
        {ws.chat.map((t, i) => {
          const q = t.askId ? asks.find((a) => a.id === t.askId) : null;
          const run = t.askId ? runs[t.askId] : null;
          const order = run?.answer?.flatMap((b) => b.citations).filter((c, j, a) => a.indexOf(c) === j) ?? [];
          const kept = t.askId ? ws.kept.includes(t.askId) : false;
          return (
            <div key={i} className="space-y-2">
              <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-ink px-3.5 py-2 text-sm text-page">{t.typed}</p>
              <div className="max-w-[95%] rounded-2xl rounded-bl-sm border border-rule p-3.5">
                {!q && <p className="text-sm text-muted">No close recorded question for this airline. Try one of the suggestions below.</p>}
                {q && q.question.toLowerCase() !== t.typed.toLowerCase() && <p className="mb-2 text-xs text-muted">Closest recorded question: “{q.question}”</p>}
                {q && !run && <p className="text-sm text-muted">Loading…</p>}
                {run && (
                  <>
                    {run.route !== "answer" && <p className="mb-2 inline-block rounded border border-del px-2 py-0.5 text-xs font-semibold text-del">{ROUTE[run.route ?? ""]}</p>}
                    {run.refusal && <p className="text-sm leading-relaxed">{run.refusal}</p>}
                    <ul className="space-y-2 text-sm leading-relaxed">
                      {run.answer?.map((b, j) => (
                        <li key={j}><BulletText bullet={b} metrics={run.metrics} cite={(c) => (order.indexOf(c) + 1) || null}
                          onCite={(c) => onCite(c, run)} onDetail={(d) => onDetail(d, run)} /></li>
                      ))}
                    </ul>
                    <button type="button" aria-pressed={kept}
                      onClick={() => update((w) => ({ ...w, kept: kept ? w.kept.filter((k) => k !== t.askId) : [...w.kept, t.askId!] }))}
                      className={`mt-3 rounded-full border px-3 py-1 text-xs font-semibold ${kept ? "border-ink bg-ink text-page" : "border-rule text-muted hover:border-ink hover:text-ink"}`}>
                      {kept ? "★ Kept in review" : "☆ Keep"}
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })}
        <div ref={end} />
      </div>
      <div className="border-t border-rule pt-3">
        {suggestions.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {suggestions.map((a) => (
              <button key={a.id} type="button" onClick={() => ask(a.question, a.id)}
                className="rounded-full border border-rule px-3 py-1 text-left text-xs hover:border-ink">{a.question}</button>
            ))}
          </div>
        )}
        <form onSubmit={(e) => { e.preventDefault(); if (text.trim()) { ask(text.trim()); setText(""); } }} className="flex gap-2">
          <label htmlFor="ask" className="sr-only">Ask a question</label>
          <input id="ask" value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about the filings…" maxLength={300}
            className="min-w-0 flex-1 rounded-full border border-rule px-4 py-2 text-sm" />
          <button type="submit" className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-page disabled:opacity-40" disabled={!text.trim()}>Ask</button>
        </form>
      </div>
    </div>
  );
}
