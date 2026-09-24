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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs text-subtext mb-1.5">{title}</div>
      {children}
    </div>
  );
}

export default function RecommendationCard({ item }: { item: RecommendationItem }) {
  const [open, setOpen] = useState(false);
  const borderColor = PRIORITY_BORDER[item.priority || "P3"];
  const steps = item.fix_steps || [];

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
            <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-emerald-500/30 text-emerald-400/90">
              PageSpeed-supported
            </span>
          </div>
          <div className="font-medium text-sm">{item.root_cause}</div>
          <p className="text-sm text-subtext mt-1 leading-relaxed">{item.summary}</p>
          {!open && (
            <span className="text-[11px] text-accent mt-2 inline-block">
              Show full diagnosis, reader impact and fix steps
            </span>
          )}
        </div>
        {open ? (
          <ChevronUp size={16} className="text-subtext shrink-0 mt-1" />
        ) : (
          <ChevronDown size={16} className="text-subtext shrink-0 mt-1" />
        )}
      </button>

      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-border/60 space-y-4">
          {item.problem_explanation && (
            <Section title="What is actually happening, and why">
              <p className="text-sm leading-relaxed text-text/90">{item.problem_explanation}</p>
            </Section>
          )}

          {item.user_impact && (
            <Section title="What this costs the reader">
              <p className="text-sm leading-relaxed text-text/90 border-l-2 border-warn/50 pl-3">
                {item.user_impact}
              </p>
            </Section>
          )}

          <Section title="Evidence this is based on">
            <ul className="space-y-1">
              {item.evidence.map((e, i) => (
                <li key={i} className="text-sm font-mono-num text-text/90 pl-3 border-l border-border">
                  {e}
                </li>
              ))}
            </ul>
          </Section>

          {item.resources.length > 0 && (
            <Section title={item.resources.length === 1 ? "Resource" : "Resources"}>
              <ul className="space-y-1">
                {item.resources.map((url) => (
                  <li
                    key={url}
                    className="text-xs font-mono-num text-accent/90 break-all pl-3 border-l border-border"
                  >
                    {url}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {item.affected_audits.length > 0 && (
            <Section title="Affected audits">
              <div className="flex flex-wrap gap-1.5">
                {item.affected_audits.map((a) => (
                  <span
                    key={a}
                    className="text-xs font-mono-num px-2 py-0.5 rounded bg-panel2 border border-border text-subtext"
                  >
                    {a}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {steps.length > 0 ? (
            <Section title="How to fix it, in order">
              <ol className="space-y-2">
                {steps.map((step, i) => (
                  <li key={i} className="text-sm leading-relaxed flex gap-2.5">
                    <span className="font-mono-num text-xs text-accent shrink-0 mt-0.5">{i + 1}.</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </Section>
          ) : (
            <Section title="Suggested fix">
              <p className="text-sm leading-relaxed">{item.suggested_fix}</p>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}