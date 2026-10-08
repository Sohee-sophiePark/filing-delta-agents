import type { Bundle, Detail } from "../types";
import { BulletText } from "./RichText";
import { Dot } from "./Status";

type Props = { b: Bundle; cite: (id: string) => number | null; onCite: (id: string) => void; onDetail: (d: Detail) => void };
const TILES = [["net_leverage", "Net leverage"], ["interest_coverage", "Interest coverage"], ["liquid_assets", "Cash + ST investments"], ["maturity_y1", "Debt due within a year"]] as const;

/** The agents' brief: key numbers, three sections, status reasons, and the full numbers on demand. */
export function Brief({ b, cite, onCite, onDetail }: Props) {
  const run = b.run, d = run.draft!, y = run.fiscal_year;
  const common = { metrics: b.metrics, cite, onCite, onDetail, signals: run.signals };
  const years = Object.keys(b.metric_rows[0]?.values ?? {});
  const max = Math.max(...b.maturities.map((m) => m.value), 1);
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-2">
        {TILES.map(([k, label]) => {
          const m = b.metrics[`${k}.${y}`], prior = b.metrics[`${k}.${y - 1}`];
          return m ? (
            <button key={k} type="button" onClick={() => onDetail({ kind: "metric", key: `${k}.${y}`, metric: m })}
              className="rounded-lg border border-rule p-3 text-left hover:border-ink">
              <span className="block text-xs text-muted">{label}</span>
              <span className="num block text-xl font-semibold">{m.display}</span>
              {prior && <span className="num block text-xs text-muted">FY{y - 1}: {prior.display}</span>}
            </button>
          ) : null;
        })}
      </div>
      <p className="text-lg font-semibold leading-snug">{d.headline}</p>
      {d.sections.map((s) => (
        <section key={s.title}>
          <h3 className="text-xs font-bold uppercase tracking-wider text-muted">{s.title}</h3>
          <ul className="mt-2 space-y-3">{s.bullets.map((x, i) => <li key={i} className="leading-relaxed"><BulletText bullet={x} {...common} /></li>)}</ul>
        </section>
      ))}
      <section className="rounded-lg bg-wash p-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-muted">Why {d.proposed_status}</h3>
        <ul className="mt-2 space-y-2">{d.status_reasons.map((x, i) => <li key={i} className="leading-relaxed"><BulletText bullet={x} {...common} /></li>)}</ul>
      </section>
      <details className="rounded-lg border border-rule">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">All numbers, signals and 8-K filings</summary>
        <div className="space-y-6 border-t border-rule p-4">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[26rem] text-sm">
              <thead><tr className="border-b border-ink text-left"><th className="py-1.5 pr-2 font-semibold">Metric</th>{years.map((yy) => <th key={yy} className="num py-1.5 text-right font-semibold">FY{yy}</th>)}</tr></thead>
              <tbody>
                {b.metric_rows.map((r) => (
                  <tr key={r.key} className="border-b border-rule">
                    <th scope="row" className="py-1.5 pr-2 text-left font-normal">{r.label}</th>
                    {years.map((yy) => {
                      const m = b.metrics[r.keys[yy]];
                      return <td key={yy} className="num py-1.5 text-right">{m ? <button type="button" className="hover:text-ins hover:underline" onClick={() => onDetail({ kind: "metric", key: r.keys[yy], metric: m })}>{r.values[yy]}</button> : "—"}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-muted">Debt maturities (FY{y} 10-K)</h4>
            <ul className="mt-2 space-y-1.5">
              {b.maturities.map((m) => (
                <li key={m.key} className="grid grid-cols-[8.5rem_minmax(0,1fr)_4.5rem] items-center gap-2 text-sm">
                  <span className="text-muted">{m.label.replace("Debt maturing ", "")}</span>
                  <span className="h-2.5 rounded-sm bg-ink" style={{ width: `${(m.value / max) * 100}%` }} />
                  <span className="num text-right">{m.display}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-muted">Code signals</h4>
            <ul className="mt-2 space-y-1.5 text-sm">
              {run.signals.map((s) => (
                <li key={s.id}><button type="button" onClick={() => onDetail({ kind: "signal", item: s })} className="flex items-start gap-2 text-left hover:underline">
                  <span className="mt-1.5"><Dot level={s.level} /></span><span><span className="num text-muted">{s.id}</span> {s.text}</span>
                </button></li>
              ))}
              {run.signals.length === 0 && <li className="text-muted">No signals at the illustrative thresholds.</li>}
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-muted">8-K filings since the 10-K</h4>
            <ul className="mt-2 divide-y divide-rule text-sm">
              {b.events.map((e) => (
                <li key={e.id} className="py-1.5"><a href={e.url} target="_blank" rel="noopener noreferrer" className="num text-ins underline">{e.filed}</a> {e.labels.join("; ")}</li>
              ))}
            </ul>
          </div>
        </div>
      </details>
    </div>
  );
}
