import { useEffect, useMemo, useRef, useState } from "react";
import type { Bundle, Highlight } from "../types";
import { Redline } from "./Redline";
import { fmtDate } from "../data";

type Docs = Bundle["documents"];
type Props = {
  docs: Docs;
  changes: Bundle["changes"];
  target: { pid: string; n: number } | null;
  cited: Set<string>;
  highlights: Highlight[];
  onHighlight: (h: Omit<Highlight, "id">) => string;
  onNote: (id: string, note: string) => void;
  onRemove: (id: string) => void;
};
type Pending = { pid: string; start: number; end: number; quote: string; x: number; y: number };

const MARK = { yellow: "bg-yellow-200", red: "bg-red-200" };
const BADGE: Record<string, string> = { added: "Added", modified: "Modified", updated: "Updated", unchanged: "Unchanged" };

function locate(docs: Docs, pid: string) {
  for (const f of docs.filings) for (const s of f.sections) if (s.paragraphs.some((p) => p.id === pid)) return { acc: f.accession, key: s.key };
  return null;
}

/** The filing itself: sections, cited paragraphs, the analyst's highlights and notes, and year-over-year changes. */
export function DocReader({ docs, changes, target, cited, highlights, onHighlight, onNote, onRemove }: Props) {
  const [acc, setAcc] = useState(docs.filings[0].accession);
  const [key, setKey] = useState(docs.filings[0].sections[0].key);
  const [showChanges, setShowChanges] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const filing = docs.filings.find((f) => f.accession === acc) ?? docs.filings[0];
  const section = filing.sections.find((s) => s.key === key) ?? filing.sections[0];
  const isTenK1A = filing.accession === docs.filings[0].accession && section.key === "1A";
  const byPid = useMemo(() => new Map(changes.filter((c) => c.paragraph).map((c) => [c.paragraph!, c])), [changes]);
  const removed = changes.filter((c) => c.status === "removed");
  const headings = useMemo(() => new Set(Object.values(docs.rf_map)), [docs]);

  useEffect(() => {
    if (!target) return;
    const at = locate(docs, target.pid);
    if (!at) return;
    setAcc(at.acc);
    setKey(at.key);
    setFlash(target.pid);
    requestAnimationFrame(() => box.current?.querySelector(`[data-pid="${CSS.escape(target.pid)}"]`)?.scrollIntoView({ block: "center" }));
    const t = setTimeout(() => setFlash(null), 2200);
    return () => clearTimeout(t);
  }, [target, docs]);

  const capture = () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return setPending(null);
    const r = sel.getRangeAt(0);
    const host = (n: Node) => (n instanceof Element ? n : n.parentElement)?.closest<HTMLElement>("[data-text]");
    const a = host(r.startContainer);
    if (!a || a !== host(r.endContainer)) return setPending(null);
    const pre = document.createRange();
    pre.selectNodeContents(a);
    pre.setEnd(r.startContainer, r.startOffset);
    const start = pre.toString().length;
    const quote = r.toString();
    if (!quote.trim()) return setPending(null);
    const rect = r.getBoundingClientRect();
    setPending({ pid: a.dataset.text!, start, end: start + quote.length, quote, x: rect.left + rect.width / 2, y: rect.top });
  };

  const add = (color: "yellow" | "red", withNote: boolean) => {
    if (!pending) return;
    const id = onHighlight({
      pid: pending.pid, start: pending.start, end: pending.end, color, quote: pending.quote.trim(), note: "",
      source: `${filing.form} filed ${filing.filed}, ${section.label}`,
    });
    window.getSelection()?.removeAllRanges();
    setPending(null);
    if (withNote) setEditing(id);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-rule px-4 py-3">
        <label className="sr-only" htmlFor="filing">Filing</label>
        <select id="filing" value={filing.accession} onChange={(e) => { setAcc(e.target.value); setKey(docs.filings.find((f) => f.accession === e.target.value)!.sections[0].key); }}
          className="rounded border border-rule bg-page px-2 py-1.5 text-sm font-semibold">
          {docs.filings.map((f) => <option key={f.accession} value={f.accession}>{f.form} · filed {fmtDate(f.filed)}</option>)}
        </select>
        <a href={filing.url} target="_blank" rel="noopener noreferrer" className="text-xs text-muted underline hover:text-ink">SEC.gov ↗</a>
        <div className="ml-auto flex flex-wrap gap-1" role="tablist" aria-label="Sections">
          {filing.sections.map((s) => (
            <button key={s.key} type="button" role="tab" aria-selected={s.key === section.key} onClick={() => setKey(s.key)}
              className={`rounded-full px-3 py-1 text-sm ${s.key === section.key ? "bg-ink text-page" : "text-muted hover:bg-wash hover:text-ink"}`}>
              {s.label}
            </button>
          ))}
        </div>
      </div>
      {isTenK1A && (
        <div className="flex flex-wrap items-center gap-3 border-b border-rule bg-wash px-4 py-2 text-sm">
          <label className="flex cursor-pointer items-center gap-2 font-semibold">
            <input type="checkbox" checked={showChanges} onChange={(e) => setShowChanges(e.target.checked)} className="h-4 w-4 accent-ins" />
            Show changes vs prior year
          </label>
          {showChanges && removed.length > 0 && (
            <details className="w-full">
              <summary className="cursor-pointer text-del">{removed.length} risk factor{removed.length > 1 ? "s" : ""} removed this year</summary>
              <ul className="mt-2 space-y-2">{removed.map((c) => <li key={c.id}><del>{c.heading}</del></li>)}</ul>
            </details>
          )}
        </div>
      )}
      <div ref={box} onMouseUp={capture} onKeyUp={capture} onTouchEnd={() => setTimeout(capture, 50)}
        className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-8">
        <article className="mx-auto max-w-[68ch] space-y-3 text-[15px] leading-7">
          {section.paragraphs.map((p) => {
            const hs = highlights.filter((h) => h.pid === p.id).sort((x, y) => x.start - y.start);
            const change = showChanges && isTenK1A ? byPid.get(p.id) : undefined;
            const segs: React.ReactNode[] = [];
            let at = 0;
            for (const h of hs) {
              let [s, e] = [h.start, h.end];
              if (p.text.slice(s, e).trim() !== h.quote) [s, e] = [p.text.indexOf(h.quote), p.text.indexOf(h.quote) + h.quote.length];
              if (s < at) continue; // overlapping, or quote no longer in this paragraph
              segs.push(p.text.slice(at, s));
              segs.push(
                <mark key={h.id} className={`${MARK[h.color]} cursor-pointer rounded-sm text-ink`} title={h.note || "Add a note"}
                  onClick={() => setEditing(h.id)}>
                  {p.text.slice(s, e)}
                </mark>,
              );
              at = e;
            }
            segs.push(p.text.slice(at));
            const isCited = cited.has(p.id);
            return (
              <div key={p.id} data-pid={p.id}
                className={`relative rounded-sm transition-colors ${isCited ? "border-l-4 border-ins pl-3" : "pl-4"} ${flash === p.id ? "bg-ins-bg" : ""}`}>
                {change && (
                  <span className={`mb-1 inline-block rounded px-1.5 text-xs font-bold uppercase ${change.status === "added" ? "bg-ins-bg text-ins" : change.status === "modified" ? "bg-del-bg text-del" : "bg-wash text-muted"}`}>
                    {BADGE[change.status]}{change.status === "modified" || change.status === "updated" ? ` · ${Math.round(change.changed * 100)}% of words` : ""}
                  </span>
                )}
                <p data-text={p.id} className={headings.has(p.id) ? "pt-2 font-semibold" : undefined}>{segs}</p>
                {change?.diff && (change.status === "modified" || change.status === "updated") && (
                  <details className="mt-1 rounded border border-rule bg-page p-2">
                    <summary className="cursor-pointer text-xs font-semibold text-muted">What changed in this risk factor</summary>
                    <div className="mt-2"><Redline diff={change.diff} /></div>
                  </details>
                )}
                {hs.filter((h) => h.note || editing === h.id).map((h) => (
                  <div key={h.id} className={`mt-1 rounded border-l-4 ${h.color === "red" ? "border-red-400" : "border-yellow-400"} bg-wash p-2 text-sm`}>
                    {editing === h.id ? (
                      <NoteEditor initial={h.note} onSave={(t) => { onNote(h.id, t); setEditing(null); }}
                        onRemove={() => { onRemove(h.id); setEditing(null); }} onCancel={() => setEditing(null)} />
                    ) : (
                      <button type="button" onClick={() => setEditing(h.id)} className="w-full text-left">✎ {h.note}</button>
                    )}
                  </div>
                ))}
              </div>
            );
          })}
        </article>
      </div>
      {pending && (
        <div role="toolbar" aria-label="Highlight selection"
          style={{ left: Math.min(Math.max(pending.x, 130), window.innerWidth - 130), top: Math.max(pending.y - 52, 8) }}
          className="fixed z-30 flex -translate-x-1/2 items-center gap-1 rounded-lg bg-ink p-1 text-sm text-page shadow-xl">
          <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => add("yellow", false)} className="flex items-center gap-1.5 rounded px-2 py-1.5 hover:bg-white/15">
            <span className="h-3 w-3 rounded-full bg-yellow-300" /> Important
          </button>
          <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => add("red", false)} className="flex items-center gap-1.5 rounded px-2 py-1.5 hover:bg-white/15">
            <span className="h-3 w-3 rounded-full bg-red-300" /> Concern
          </button>
          <span className="mx-0.5 h-5 w-px bg-white/30" />
          <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => add("yellow", true)} className="whitespace-nowrap rounded px-2 py-1.5 hover:bg-white/15">✎ Note</button>
        </div>
      )}
    </div>
  );
}

function NoteEditor({ initial, onSave, onRemove, onCancel }: { initial: string; onSave: (t: string) => void; onRemove: () => void; onCancel: () => void }) {
  const [text, setText] = useState(initial);
  return (
    <div>
      <label className="sr-only" htmlFor="note-edit">Note</label>
      <textarea id="note-edit" autoFocus value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={500}
        className="w-full rounded border border-rule bg-page p-2 text-sm" placeholder="Your note" />
      <div className="mt-1 flex gap-2 text-xs">
        <button type="button" onClick={() => onSave(text.trim())} className="rounded bg-ink px-2.5 py-1 font-semibold text-page">Save</button>
        <button type="button" onClick={onCancel} className="rounded px-2 py-1 text-muted hover:text-ink">Cancel</button>
        <button type="button" onClick={onRemove} className="ml-auto rounded px-2 py-1 text-del hover:underline">Remove highlight</button>
      </div>
    </div>
  );
}
