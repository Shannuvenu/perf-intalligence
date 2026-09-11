"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { RecommendationItem } from "@/types";
import PriorityBadge from "./PriorityBadge";

const PRIORITY_BORDER: Record<string, string> = {
  P0: "border-l-crit",
  P1: "border-l-[#e8823d]",
  P2: "border-l-warn",
  P3: "border-l-border",
};

export default function RecommendationCard({ item }: { item: RecommendationItem }) {
  const [open, setOpen] = useState(false);
  const borderColor = PRIORITY_BORDER[item.priority || "P3"];

  return (
    <div className={`border border-border ${borderColor} border-l-4 bg-panel rounded`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-start justify-between gap-4 px-4 py-3.5 text-left"
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <PriorityBadge priority={item.priority} />
            <span className="text-[11px] text-subtext">
              Impact: <span className="text-text">{item.impact}</span> · Ease:{" "}
              <span className="text-text">{item.ease_of_fix}</span> · Confidence:{" "}
              <span className="font-mono-num text-text">{Math.round(item.confidence * 100)}%</span>
            </span>
          </div>
          <div className="font-medium text-sm">{item.root_cause}</div>
          <p className="text-sm text-subtext mt-1 leading-relaxed">{item.summary}</p>
        </div>
        {open ? <ChevronUp size={16} className="text-subtext shrink-0 mt-1" /> : <ChevronDown size={16} className="text-subtext shrink-0 mt-1" />}
      </button>

      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-border/60 space-y-3">
          <div>
            <div className="text-xs text-subtext mb-1.5">Evidence</div>
            <ul className="space-y-1">
              {item.evidence.map((e, i) => (
                <li key={i} className="text-sm font-mono-num text-text/90 pl-3 border-l border-border">
                  {e}
                </li>
              ))}
            </ul>
          </div>

          {item.affected_audits.length > 0 && (
            <div>
              <div className="text-xs text-subtext mb-1.5">Affected audits</div>
              <div className="flex flex-wrap gap-1.5">
                {item.affected_audits.map((a) => (
                  <span key={a} className="text-xs font-mono-num px-2 py-0.5 rounded bg-panel2 border border-border text-subtext">
                    {a}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div>
            <div className="text-xs text-subtext mb-1.5">Suggested fix</div>
            <p className="text-sm leading-relaxed">{item.suggested_fix}</p>
          </div>
        </div>
      )}
    </div>
  );
}
