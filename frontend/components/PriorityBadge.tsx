const STYLES: Record<string, string> = {
  P0: "text-crit border-crit/40 bg-crit/10",
  P1: "text-[#e8823d] border-[#e8823d]/40 bg-[#e8823d]/10",
  P2: "text-warn border-warn/40 bg-warn/10",
  P3: "text-subtext border-border bg-panel2",
};

const LABELS: Record<string, string> = {
  P0: "P0 · Critical",
  P1: "P1 · High",
  P2: "P2 · Medium",
  P3: "P3 · Low",
};

export default function PriorityBadge({ priority }: { priority: string | null }) {
  const key = priority && STYLES[priority] ? priority : "P3";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium border ${STYLES[key]}`}>
      {LABELS[key]}
    </span>
  );
}
