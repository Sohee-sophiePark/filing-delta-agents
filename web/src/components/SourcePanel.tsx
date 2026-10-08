import { useEffect } from "react";
import type { Detail, Metric } from "../types";

type Props = { detail: Detail | null; metrics: Record<string, Metric>; onDetail: (d: Detail) => void; onClose: () => void };

/** Dialog explaining a metric (formula and inputs, or the reported XBRL fact) or a code signal. */
export function DetailDialog({ detail, metrics, onDetail, onClose }: Props) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  if (!detail) return null;
  const link = (k: string) => (
    <button type="button" className="num text-left text-ins underline" onClick={() => onDetail({ kind: "metric", key: k, metric: metrics[k] })}>
      {metrics[k].label} FY{metrics[k].year}: {metrics[k].display}
    </button>
  );
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-ink/30 p-0 sm:items-center sm:p-6" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Details" onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-t-lg bg-page p-5 shadow-2xl sm:rounded-lg">
        <div className="flex items-start justify-between gap-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            {detail.kind === "metric" ? `Metric · FY${detail.metric.year}` : `Code signal ${detail.item.id} · ${detail.item.level}`}
          </p>
          <button type="button" onClick={onClose} aria-label="Close" className="-mt-1 rounded px-2 text-lg text-muted hover:text-ink">✕</button>
        </div>
        {detail.kind === "signal" ? (
          <>
            <p className="mt-2">{detail.item.text}</p>
            <p className="mt-3 text-xs text-muted">Computed by code from:</p>
            <ul className="mt-1 space-y-1 text-sm">
              {detail.item.refs.map((r) => <li key={r}>{metrics[r] ? link(r) : <span className="num text-muted">{r}</span>}</li>)}
            </ul>
            <p className="mt-3 text-xs text-muted">Thresholds are illustrative for this demo, not a credit methodology.</p>
          </>
        ) : (
          <>
            <p className="mt-1 font-semibold">{detail.metric.label}</p>
            <p className="num mt-2 text-3xl font-semibold">{detail.metric.display}</p>
            {detail.metric.formula ? (
              <>
                <p className="mt-4 text-xs text-muted">Computed by code</p>
                <p className="num mt-1 text-sm">{detail.metric.formula}</p>
                <ul className="mt-2 space-y-1 text-sm">{(detail.metric.inputs ?? []).filter((k) => metrics[k]).map((k) => <li key={k}>{link(k)}</li>)}</ul>
              </>
            ) : detail.metric.source && (
              <>
                <p className="mt-4 text-xs text-muted">Reported XBRL fact</p>
                <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                  <dt className="text-muted">Concept</dt><dd className="num break-all">{detail.metric.source.concept}</dd>
                  <dt className="text-muted">Fact id</dt><dd className="num">{detail.metric.source.fact_id}</dd>
                  <dt className="text-muted">Filing</dt><dd>{detail.metric.source.form} filed {detail.metric.source.filed}</dd>
                </dl>
                <a className="mt-4 inline-block text-sm font-semibold text-ins underline" href={detail.metric.source.url} target="_blank" rel="noopener noreferrer">
                  Open the filing on SEC.gov ↗
                </a>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
