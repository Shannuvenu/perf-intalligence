"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import RecommendationCard from "@/components/RecommendationCard";
import type { RecommendationItem } from "@/types";

export default function QuickAnalyzePage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<RecommendationItem[] | null>(null);
  const [modelName, setModelName] = useState<string | null>(null);

  async function handleAnalyze() {
    setError(null);
    setResults(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(input);
    } catch {
      setError("That doesn't look like valid JSON. Paste the full PageSpeed Insights / Lighthouse report.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.quickAnalyze(parsed);
      setResults(res.recommendations);
      setModelName(res.model_name);
      if (res.recommendations.length === 0) {
        setError(res.note || "No issues surfaced from this report - metrics may already be healthy.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not analyze this report.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Quick Analyze</h1>
        <p className="text-sm text-subtext mt-1">
          Paste a raw PageSpeed Insights / Lighthouse JSON report - from anywhere, not just a monitored URL -
          and get the top 5 issues ranked by impact, with a fix for each.
        </p>
      </header>

      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder='Paste the full report JSON here, e.g. { "lighthouseResult": { ... } }'
        rows={12}
        className="w-full bg-panel border border-border rounded px-3 py-2 text-xs font-mono-num outline-none focus:border-accent resize-y"
      />

      <div className="mt-3 flex items-center gap-3">
        <button
          onClick={handleAnalyze}
          disabled={loading || !input.trim()}
          className="px-3.5 py-2 rounded text-sm font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Analyzing..." : "Analyze report"}
        </button>
        {modelName && !loading && (
          <span className="text-xs text-subtext">Analyzed by {modelName}</span>
        )}
      </div>

      {error && (
        <div className="mt-4 border border-crit/40 bg-crit/5 text-crit rounded p-4 text-sm">{error}</div>
      )}

      {results && results.length > 0 && (
        <div className="mt-6 space-y-3">
          <h2 className="text-sm font-medium text-subtext">Top {results.length} issues, ranked by impact</h2>
          {results.map((item, i) => (
            <RecommendationCard key={i} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}