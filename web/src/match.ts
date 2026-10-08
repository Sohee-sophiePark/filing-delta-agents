const STOP = new Set("a an and are as at be by did do does for from has have how in is it its of on or our that the this to was we were what when which will with".split(" "));
const words = (t: string) => new Set(t.toLowerCase().match(/[a-z0-9]+/g)?.filter((w) => !STOP.has(w)) ?? []);

/** Closest recorded question by word overlap (Jaccard); null below `min`. */
export function closest<T extends { question: string }>(typed: string, options: T[], min = 0.25): T | null {
  const q = words(typed);
  let best: T | null = null;
  let score = 0;
  for (const o of options) {
    const w = words(o.question);
    const inter = [...q].filter((x) => w.has(x)).length;
    const s = inter / (new Set([...q, ...w]).size || 1);
    if (s > score) [best, score] = [o, s];
  }
  return score >= min ? best : null;
}
