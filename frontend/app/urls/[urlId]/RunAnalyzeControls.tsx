"use client";

import { api, ApiError } from "@/lib/api";
import ActionButton from "@/components/ActionButton";

export default function RunAnalyzeControls({ urlId, runCount }: { urlId: number; runCount: number }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <ActionButton
        label="Run PageSpeed"
        runningLabel="Running PSI, stabilizing, analyzing..."
        action={async () => {
          try {
            const res = await api.runFullAnalysis(urlId);
            return { ok: res.analyzed, message: res.analyzed ? undefined : res.message };
          } catch (err) {
            return { ok: false, message: err instanceof ApiError ? err.message : "Something went wrong." };
          }
        }}
      />
      <span className="text-xs text-subtext">{runCount} run{runCount === 1 ? "" : "s"} recorded</span>
    </div>
  );
}