import type { Bullet, Detail, Metric, Signal } from "../types";

const PLACEHOLDER = /\{\{m:([a-z0-9_.]+)\}\}/g;

type Props = {
  bullet: Bullet;
  metrics: Record<string, Metric>;
  cite: (id: string) => number | null;
  onCite: (id: string) => void;
  onDetail: (d: Detail) => void;
  signals?: Signal[];
};

/** Bullet text with metric values and citations as buttons (metrics open details, citations open the filing). */
export function BulletText({ bullet, metrics, cite, onCite, onDetail, signals = [] }: Props) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const m of bullet.text.matchAll(PLACEHOLDER)) {
    parts.push(bullet.text.slice(last, m.index));
    const metric = metrics[m[1]];
    parts.push(
      metric ? (
        <button key={m.index} type="button" onClick={() => onDetail({ kind: "metric", key: m[1], metric })}
          className="num rounded px-0.5 font-semibold underline decoration-dotted decoration-2 underline-offset-4 hover:bg-ins-bg"
          title={`${metric.label}: how it was computed`}>
          {metric.display}
        </button>
      ) : m[0],
    );
    last = (m.index ?? 0) + m[0].length;
  }
  parts.push(bullet.text.slice(last));
  return (
    <>
      {parts}
      {bullet.citations.map((c) => {
        const n = cite(c);
        return n ? (
          <button key={c} type="button" onClick={() => onCite(c)} title="Show in the filing"
            className="num ml-1 inline-flex h-6 min-w-6 items-center justify-center rounded bg-ins-bg px-1 align-[0.15em] text-xs font-semibold text-ins hover:bg-ins hover:text-page">
            {n}
          </button>
        ) : null;
      })}
      {(bullet.signals ?? []).map((sid) => {
        const s = signals.find((x) => x.id === sid);
        return s ? (
          <button key={sid} type="button" onClick={() => onDetail({ kind: "signal", item: s })} title={s.text}
            className="num ml-1 inline-flex h-6 items-center rounded border border-rule px-1.5 align-[0.15em] text-xs text-muted hover:border-ink hover:text-ink">
            {sid}
          </button>
        ) : null;
      })}
    </>
  );
}
