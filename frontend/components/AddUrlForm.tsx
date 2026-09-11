"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { UrlCategory } from "@/types";

export default function AddUrlForm({ siteId }: { siteId: number }) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState<UrlCategory>("article");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createUrl(siteId, url, category);
      setUrl("");
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add URL.");
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
        <Plus size={14} /> Add URL
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="border border-border bg-panel rounded p-4 space-y-3 max-w-md">
      <div>
        <label className="text-xs text-subtext block mb-1">URL</label>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          placeholder="https://www.deccanherald.com/district/..."
          className="w-full bg-panel2 border border-border rounded px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </div>
      <div>
        <label className="text-xs text-subtext block mb-1">Category</label>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value as UrlCategory)}
          className="w-full bg-panel2 border border-border rounded px-3 py-2 text-sm outline-none focus:border-accent"
        >
          <option value="homepage">Homepage</option>
          <option value="article">Article</option>
          <option value="category">Category</option>
          <option value="other">Other</option>
        </select>
      </div>
      {error && <p className="text-xs text-crit">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="px-3.5 py-2 rounded text-sm font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-60"
        >
          {submitting ? "Adding..." : "Add URL"}
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
