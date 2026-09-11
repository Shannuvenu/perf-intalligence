"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MetricTrend } from "@/types";

const DIRECTION_STYLE: Record<string, { label: string; color: string }> = {
  improving: { label: "Improving", color: "#34c283" },
  stable: { label: "Stable", color: "#8993a4" },
  regressing: { label: "Regressing", color: "#f0564d" },
  insufficient_data: { label: "Not enough data", color: "#8993a4" },
};

const METRIC_LABELS: Record<string, string> = {
  performance_score: "Performance score",
  accessibility_score: "Accessibility score",
  lcp_ms: "LCP (ms)",
  cls: "CLS",
  tbt_ms: "TBT (ms)",
  fcp_ms: "FCP (ms)",
};

export default function TrendChart({ trend }: { trend: MetricTrend }) {
  const data = trend.points.map((p) => ({
    ts: new Date(p.timestamp).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    value: p.value,
  }));
  const dir = DIRECTION_STYLE[trend.direction];

  return (
    <div className="border border-border bg-panel rounded p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium">{METRIC_LABELS[trend.metric] || trend.metric}</span>
        <span className="text-xs px-2 py-0.5 rounded border" style={{ color: dir.color, borderColor: `${dir.color}66` }}>
          {dir.label}
        </span>
      </div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <XAxis dataKey="ts" tick={{ fontSize: 11, fill: "#8993a4" }} axisLine={{ stroke: "#232935" }} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#8993a4" }} axisLine={false} tickLine={false} width={40} />
            <Tooltip
              contentStyle={{ background: "#171c25", border: "1px solid #232935", borderRadius: 4, fontSize: 12 }}
              labelStyle={{ color: "#8993a4" }}
            />
            <Line type="monotone" dataKey="value" stroke={dir.color} strokeWidth={2} dot={{ r: 3 }} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
