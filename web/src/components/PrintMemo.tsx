import type { Memo } from "../memo";

/** Print-only review memo; hidden on screen. */
export function PrintMemo({ m }: { m: Memo }) {
  const refs = (r: number[]) => (r.length ? <sup className="num"> {r.join(",")}</sup> : null);
  return (
    <div className="print-only text-[11pt] leading-snug">
      <h1 className="text-xl font-bold">{m.title}</h1>
      {m.meta.map((x) => <p key={x} className="text-sm text-muted">{x}</p>)}
      <p className="mt-3 font-semibold">{m.headline}</p>
      {m.sections.map((s) => (
        <section key={s.title} className="mt-3">
          <h2 className="font-bold">{s.title}</h2>
          <ul className="ml-5 list-disc">{s.items.map((i, k) => <li key={k}>{i.text}{refs(i.refs)}</li>)}</ul>
        </section>
      ))}
      <h2 className="mt-3 font-bold">Key numbers</h2>
      <table className="w-full text-sm">
        <thead><tr><th className="text-left">Metric</th>{m.years.map((y) => <th key={y} className="text-right">FY{y}</th>)}</tr></thead>
        <tbody>{m.numbers.map((r) => <tr key={r.label}><td>{r.label}</td>{r.values.map((v, k) => <td key={k} className="num text-right">{v ?? "—"}</td>)}</tr>)}</tbody>
      </table>
      {m.kept.length > 0 && <h2 className="mt-3 font-bold">Kept questions</h2>}
      {m.kept.map((k) => (
        <div key={k.question} className="mt-1">
          <p className="font-semibold">Q: {k.question}</p>
          {k.refusal ? <p>{k.refusal}</p> : <ul className="ml-5 list-disc">{k.items.map((i, j) => <li key={j}>{i.text}{refs(i.refs)}</li>)}</ul>}
        </div>
      ))}
      {m.highlights.length > 0 && <h2 className="mt-3 font-bold">Highlights and notes</h2>}
      <ul className="ml-5 list-disc">{m.highlights.map((h, k) => <li key={k}><b>{h.kind}</b>: “{h.quote}” ({h.source}){h.note && <><br />Note: {h.note}</>}</li>)}</ul>
      <h2 className="mt-3 font-bold">Sources</h2>
      <ol className="ml-5 list-decimal text-sm">{m.sources.map((s) => <li key={s.n}>{s.label}: {s.url}</li>)}</ol>
    </div>
  );
}
