import { useEffect, useState } from "react";
import type { Workspace } from "./types";

const EMPTY: Workspace = { chat: [], kept: [], highlights: [], decision: null };
const key = (ticker: string) => `filing-delta.v1.${ticker}`;

/** Per-airline workspace (chat, kept Q&A, highlights, decision) persisted in this browser only. */
export function useWorkspace(ticker: string): [Workspace, (f: (w: Workspace) => Workspace) => void] {
  const [ws, setWs] = useState<Workspace>(() => ({ ...EMPTY, ...JSON.parse(localStorage.getItem(key(ticker)) ?? "{}") }));
  useEffect(() => { setWs({ ...EMPTY, ...JSON.parse(localStorage.getItem(key(ticker)) ?? "{}") }); }, [ticker]);
  const update = (f: (w: Workspace) => Workspace) =>
    setWs((w) => {
      const next = f(w);
      localStorage.setItem(key(ticker), JSON.stringify(next));
      return next;
    });
  return [ws, update];
}
