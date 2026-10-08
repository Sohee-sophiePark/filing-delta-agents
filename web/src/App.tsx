import { useEffect, useState } from "react";
import type { Bundle, Index } from "./types";
import { fmtDate, load } from "./data";
import { Coverage } from "./pages/Coverage";
import { Workspace } from "./pages/Review";

const useRoute = () => {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash.replace(/^#\/?/, "").split("/").filter(Boolean);
};

export function App() {
  const [index, setIndex] = useState<Index | null>(null);
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState("");
  const route = useRoute();
  const ticker = ["w", "r"].includes(route[0]) ? route[1] : undefined;
  useEffect(() => { load<Index>("index").then(setIndex).catch((e) => setError(String(e))); }, []);
  useEffect(() => {
    setBundle(null);
    if (ticker) load<Bundle>(ticker).then(setBundle).catch((e) => setError(String(e)));
  }, [ticker]);
  return (
    <div className="flex h-dvh flex-col">
      <div className="screen-only border-b border-rule bg-wash px-4 py-1.5 text-center text-xs text-muted">
        Replay demo of recorded agent runs over public SEC filings{index ? ` (latest 10-K filed ${fmtDate(index.latest_10k)})` : ""}.
        Watch status is illustrative, not a credit rating. Not investment advice.
      </div>
      {!ticker && (
        <header className="screen-only mx-auto flex w-full max-w-6xl items-center px-4 pt-4">
          <a href="#/" className="text-lg font-black tracking-tight">
            <del className="bg-transparent">Filing</del> <ins className="bg-transparent">Delta</ins> <span className="font-semibold text-muted">Agents</span>
          </a>
        </header>
      )}
      {error && <p role="alert" className="p-4 text-del">Could not load demo data: {error}</p>}
      {index && !ticker && <Coverage index={index} />}
      {index && ticker && bundle && <Workspace b={bundle} index={index} />}
    </div>
  );
}
