const TONE: Record<string, string> = {
  Stable: "text-stable border-stable",
  Monitor: "text-monitor border-monitor",
  Watchlist: "text-watch border-watch",
};

export function StatusChip({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-sm font-semibold ${TONE[status] ?? ""}`}>
      <span aria-hidden className="h-2 w-2 rounded-full bg-current" />
      {status}
    </span>
  );
}

const LEVEL: Record<string, string> = { red: "bg-watch", amber: "bg-monitor", green: "bg-stable" };

export function Dot({ level, label }: { level: string; label?: string }) {
  return <span role="img" aria-label={label ?? level} className={`inline-block h-2.5 w-2.5 rounded-full ${LEVEL[level]}`} />;
}
