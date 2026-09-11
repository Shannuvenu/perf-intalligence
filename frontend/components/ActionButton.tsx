"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { ApiError } from "@/lib/api";

type Status = "idle" | "running" | "done" | "failed";

export default function ActionButton({
  label,
  runningLabel,
  action,
  variant = "primary",
}: {
  label: string;
  runningLabel: string;
  action: () => Promise<{ ok: boolean; message?: string }>;
  variant?: "primary" | "secondary";
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const router = useRouter();

  const base =
    variant === "primary"
      ? "bg-accent text-white hover:bg-accent/90"
      : "bg-panel2 text-text border border-border hover:bg-panel2/70";

  async function handleClick() {
    setStatus("running");
    setMessage(null);
    try {
      const result = await action();
      setStatus(result.ok ? "done" : "failed");
      setMessage(result.message || null);
      router.refresh();
    } catch (err) {
      setStatus("failed");
      setMessage(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setTimeout(() => setStatus("idle"), 2500);
    }
  }

  return (
    <div className="inline-flex flex-col items-start gap-1.5">
      <button
        onClick={handleClick}
        disabled={status === "running"}
        className={`inline-flex items-center gap-2 px-3.5 py-2 rounded text-sm font-medium transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${base}`}
      >
        {status === "running" && <Loader2 size={14} className="animate-spin" />}
        {status === "running" ? runningLabel : status === "done" ? "Completed" : status === "failed" ? "Failed" : label}
      </button>
      {message && status === "failed" && <p className="text-xs text-crit max-w-xs">{message}</p>}
    </div>
  );
}
