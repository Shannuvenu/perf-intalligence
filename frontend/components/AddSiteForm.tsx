"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";

export default function AddSiteForm() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createSite(name, baseUrl);
      setName("");
      setBaseUrl("");
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create site.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 px-3 py-2 rounded text-sm border border-border bg-panel2 hover:bg-panel2/70"
      >
        <Plus size={14} /> Add site
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="border border-border bg-panel rounded p-4 space-y-3 max-w-md">
      <div>
        <label className="text-xs text-subtext block mb-1">Site name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          placeholder="e.g. Deccan Herald"
          className="w-full bg-panel2 border border-border rounded px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </div>
      <div>
        <label className="text-xs text-subtext block mb-1">Base URL</label>
        <input
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          required
          placeholder="https://www.example.com/"
          className="w-full bg-panel2 border border-border rounded px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </div>
      {error && <p className="text-xs text-crit">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="px-3.5 py-2 rounded text-sm font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-60"
        >
          {submitting ? "Adding..." : "Add site"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="px-3.5 py-2 rounded text-sm border border-border text-subtext hover:text-text"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
