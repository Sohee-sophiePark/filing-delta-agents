const KEEP = 24; // words of unchanged context kept around each change

export function Redline({ diff }: { diff: [string, string][] }) {
  return (
    <p className="text-sm leading-7">
      {diff.map(([op, text], i) => {
        if (op === "insert") return <ins key={i}>{text} </ins>;
        if (op === "delete") return <del key={i}>{text} </del>;
        const w = text.split(" ");
        if (w.length <= KEEP * 2) return <span key={i}>{text} </span>;
        const head = i === 0 ? "" : w.slice(0, KEEP).join(" ");
        const tail = i === diff.length - 1 ? "" : w.slice(-KEEP).join(" ");
        return <span key={i}>{head} <span className="text-muted">[…]</span> {tail} </span>;
      })}
    </p>
  );
}
