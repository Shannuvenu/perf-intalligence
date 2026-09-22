"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import MetricCard from "@/components/MetricCard";
import RecommendationCard from "@/components/RecommendationCard";
import type { RecommendationItem } from "@/types";
import type { QuickAnalyzeResult } from "@/lib/api";

function metricStatus(value: number | null | undefined, good: number, poor: number, lowerIsBetter = true) {
  if (value === null || value === undefined) return "neutral" as const;
  if (lowerIsBetter) {
    if (value <= good) return "good" as const;
    if (value >= poor) return "crit" as const;
    return "warn" as const;
  }
  if (value >= good) return "good" as const;
  if (value <= poor) return "crit" as const;
  return "warn" as const;
}

function ResultsPanel({
  loading,
  error,
  results,
  modelName,
}: {
  loading: boolean;
  error: string | null;
  results: QuickAnalyzeResult | null;
  modelName: string | null;
}) {
  const cws = results?.core_web_vitals || {};
  const cats = results?.category_scores || {};
  const items: RecommendationItem[] = results?.recommendations || [];

  return (
    <>
      {modelName && !loading && <p className="text-xs text-subtext mt-3">Analyzed by {modelName}</p>}

      {error && <div className="mt-4 border border-crit/40 bg-crit/5 text-crit rounded p-4 text-sm">{error}</div>}

      {results && (cats.performance !== undefined || cws.lcp_ms !== undefined) && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3 mt-6">
          <MetricCard label="Performance" value={cats.performance ?? null} status={metricStatus(cats.performance, 90, 50, false)} />
          <MetricCard label="Accessibility" value={cats.accessibility ?? null} status={metricStatus(cats.accessibility, 90, 70, false)} />
          <MetricCard label="LCP" value={cws.lcp_ms ? Math.round(cws.lcp_ms) : null} unit="ms" status={metricStatus(cws.lcp_ms, 2500, 4000)} />
          <MetricCard label="CLS" value={cws.cls ?? null} status={metricStatus(cws.cls, 0.1, 0.25)} />
          <MetricCard label="TBT" value={cws.tbt_ms ? Math.round(cws.tbt_ms) : null} unit="ms" status={metricStatus(cws.tbt_ms, 200, 600)} />
          <MetricCard label="FCP" value={cws.fcp_ms ? Math.round(cws.fcp_ms) : null} unit="ms" status={metricStatus(cws.fcp_ms, 1800, 3000)} />
          <MetricCard
            label="Bandwidth"
            value={cws.total_bytes ? (cws.total_bytes / 1_000_000).toFixed(1) : null}
            unit="MB"
            status={metricStatus(cws.total_bytes, 1_800_000, 3_000_000)}
          />
        </div>
      )}

      {items.length > 0 && (
        <div className="mt-6 space-y-3">
          <h2 className="text-sm font-medium text-subtext">Top {items.length} issues, ranked by impact</h2>
          {items.map((item, i) => (
            <RecommendationCard key={i} item={item} />
          ))}
        </div>
      )}
    </>
  );
}

function QuickAnalyzeInner() {
  const searchParams = useSearchParams();
  const prefillUrl = searchParams.get("url") || "";

  const [mode, setMode] = useState<"url" | "json">("url");
  const [urlInput, setUrlInput] = useState(prefillUrl);
  const [jsonInput, setJsonInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<QuickAnalyzeResult | null>(null);
  const [modelName, setModelName] = useState<string | null>(null);

  async function runAnalysis(fn: () => Promise<QuickAnalyzeResult>) {
    setError(null);
    setResults(null);
    setModelName(null);
    setLoading(true);
    try {
      const res = await fn();
      setResults(res);
      setModelName(res.model_name);
      if (res.recommendations.length === 0) {
        setError(res.note || "No issues surfaced - metrics may already be healthy.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not complete this analysis.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunUrl() {
    if (!urlInput.trim()) return;
    await runAnalysis(() => api.quickAnalyzeUrl(urlInput.trim()));
  }

  async function handleAnalyzeJson() {
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonInput);
    } catch {
      setError("That doesn't look like valid JSON. Paste the full PageSpeed Insights / Lighthouse report.");
      return;
    }
    await runAnalysis(() => api.quickAnalyze(parsed));
  }

  // Deep-link support: ?url=... (used by the Apps Script Alerts sheet to
  // jump straight into a deep-dive analysis of a flagged URL).
  useEffect(() => {
    if (prefillUrl) {
      handleRunUrl();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Perf Intelligence</h1>
        <p className="text-sm text-subtext mt-1">Analyze any webpage - paste a URL and run PageSpeed, no setup required.</p>
      </header>

      {mode === "url" ? (
        <>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://www.deccanherald.com/..."
              className="flex-1 bg-panel border border-border rounded px-3 py-2 text-sm outline-none focus:border-accent"
            />
            <button
              onClick={handleRunUrl}
              disabled={loading || !urlInput.trim()}
              className="px-3.5 py-2 rounded text-sm font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {loading ? "Running PageSpeed..." : "Run PageSpeed"}
            </button>
          </div>
          <button
            onClick={() => setMode("json")}
            className="text-xs text-subtext hover:text-accent mt-3 underline underline-offset-2"
          >
            Have a raw PageSpeed/Lighthouse JSON report instead? Paste it here.
          </button>
        </>
      ) : (
        <>
          <textarea
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
            placeholder='Paste the full report JSON here, e.g. { "lighthouseResult": { ... } }'
            rows={12}
            className="w-full bg-panel border border-border rounded px-3 py-2 text-xs font-mono-num outline-none focus:border-accent resize-y"
          />
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={handleAnalyzeJson}
              disabled={loading || !jsonInput.trim()}
              className="px-3.5 py-2 rounded text-sm font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Analyzing..." : "Analyze report"}
            </button>
            <button onClick={() => setMode("url")} className="text-xs text-subtext hover:text-accent underline underline-offset-2">
              Back to paste-a-URL
            </button>
          </div>
        </>
      )}

      <ResultsPanel loading={loading} error={error} results={results} modelName={modelName} />
    </div>
  );
}

export default function QuickAnalyzePage() {
  return (
    <Suspense fallback={null}>
      <QuickAnalyzeInner />
    </Suspense>
  );
}