export default function MetricCard({
  label,
  value,
  unit,
  status,
}: {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  status?: "good" | "warn" | "crit" | "neutral";
}) {
  const statusColor =
    status === "good" ? "text-good" : status === "warn" ? "text-warn" : status === "crit" ? "text-crit" : "text-text";

  return (
    <div className="border border-border bg-panel rounded px-4 py-3">
      <div className="text-xs text-subtext mb-1.5">{label}</div>
      <div className={`font-mono-num text-xl font-medium ${statusColor}`}>
        {value === null || value === undefined ? "—" : value}
        {value !== null && value !== undefined && unit ? (
          <span className="text-sm text-subtext ml-1">{unit}</span>
        ) : null}
      </div>
    </div>
  );
}
