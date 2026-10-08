import type { Index } from "../types";
import { Dot, StatusChip } from "../components/Status";
import { fmtDate } from "../data";

/** Home: one card per airline. */
export function Coverage({ index }: { index: Index }) {
  return (
    <div className="mx-auto w-full max-w-6xl overflow-y-auto px-4 py-8">
      <h1 className="max-w-3xl text-3xl font-black leading-tight tracking-tight sm:text-4xl">
        What changed in each airline's latest 10-K, and does it change the credit view?
      </h1>
      <p className="mt-3 max-w-2xl text-muted">
        Agents draft a cited annual review from public SEC filings. Code computes every number from XBRL and checks every
        citation. You read the filing alongside, ask questions, highlight, note, decide and print.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {index.coverage.map((c) => (
          <a key={c.ticker} href={`#/w/${c.ticker}`}
            className="group flex flex-col rounded-xl border border-rule p-5 transition hover:border-ink hover:shadow-lg">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xl font-bold">{c.name}</p>
                <p className="text-xs text-muted">FY{c.fiscal_year} 10-K filed {fmtDate(c.current_10k.filed)}</p>
              </div>
              <StatusChip status={c.status} />
            </div>
            <p className="mt-3 line-clamp-3 text-sm text-muted">{c.headline}</p>
            <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-rule pt-4">
              {([["Net leverage", c.net_leverage, c.net_leverage_prior ? `was ${c.net_leverage_prior}` : ""], ["Interest cover", c.interest_coverage, ""], ["Cash + ST inv.", c.liquid_assets, ""]] as const).map(([l, v, sub]) => (
                <div key={l}>
                  <dt className="text-xs text-muted">{l}</dt>
                  <dd className="num text-lg font-semibold">{v ?? "—"}</dd>
                  {sub && <dd className="num text-xs text-muted">{sub}</dd>}
                </div>
              ))}
            </dl>
            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              <span>
                Risk factors: {c.changes.added > 0 && <><ins>+{c.changes.added} new</ins> · </>}
                {c.changes.removed > 0 && <><del>−{c.changes.removed} removed</del> · </>}
                {c.changes.modified} reworded
              </span>
              <span className="flex items-center gap-1.5 text-muted">
                {(["red", "amber", "green"] as const).map((lv) => c.signals[lv] > 0 && (
                  <span key={lv} className="flex items-center gap-1"><Dot level={lv} label={`${lv} signals`} />{c.signals[lv]}</span>
                ))}
              </span>
            </div>
            <span className="mt-4 text-sm font-semibold text-ins group-hover:underline">Open workspace →</span>
          </a>
        ))}
      </div>
    </div>
  );
}
