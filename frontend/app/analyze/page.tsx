"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { api, ApiError } from "@/lib/api";
import type {
  MonitoringUrl,
  QuickAnalyzeResult,
} from "@/lib/api";

import MetricCard from "@/components/MetricCard";
import RecommendationCard from "@/components/RecommendationCard";

import type { RecommendationItem } from "@/types";

function metricStatus(
  value: number | null | undefined,
  good: number,
  poor: number,
  lowerIsBetter = true
) {
  if (value === null || value === undefined) {
    return "neutral" as const;
  }

  if (lowerIsBetter) {
    if (value <= good) {
      return "good" as const;
    }

    if (value >= poor) {
      return "crit" as const;
    }

    return "warn" as const;
  }

  if (value >= good) {
    return "good" as const;
  }

  if (value <= poor) {
    return "crit" as const;
  }

  return "warn" as const;
}

// -----------------------------------------------------------------------------
// Results Panel
// -----------------------------------------------------------------------------

function ResultsPanel({
  loading,
  error,
  note,
  results,
  modelName,
}: {
  loading: boolean;
  error: string | null;
  note: string | null;
  results: QuickAnalyzeResult | null;
  modelName: string | null;
}) {
  const cws = results?.core_web_vitals || {};
  const cats = results?.category_scores || {};
  const items: RecommendationItem[] =
    results?.recommendations || [];

  return (
    <>
      {modelName && !loading && (
        <p className="text-xs text-subtext mt-3">
          Analyzed by {modelName}
        </p>
      )}

      {results?.analyzed_url && !loading && (
        <p className="text-xs text-subtext mt-1 break-all">
          Analyzed URL:{" "}
          <span className="font-mono-num text-text/90">
            {results.analyzed_url}
          </span>
        </p>
      )}

      {error && (
        <div className="mt-4 border border-crit/40 bg-crit/5 text-crit rounded p-4 text-sm">
          {error}
        </div>
      )}

      {results &&
        (cats.performance !== undefined ||
          cws.lcp_ms !== undefined) && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3 mt-6">
            <MetricCard
              label="Performance"
              value={cats.performance ?? null}
              status={metricStatus(
                cats.performance,
                90,
                50,
                false
              )}
            />

            <MetricCard
              label="Accessibility"
              value={cats.accessibility ?? null}
              status={metricStatus(
                cats.accessibility,
                90,
                70,
                false
              )}
            />

            <MetricCard
              label="LCP"
              value={
                cws.lcp_ms
                  ? Math.round(cws.lcp_ms)
                  : null
              }
              unit="ms"
              status={metricStatus(
                cws.lcp_ms,
                2500,
                4000
              )}
            />

            <MetricCard
              label="CLS"
              value={cws.cls ?? null}
              status={metricStatus(
                cws.cls,
                0.1,
                0.25
              )}
            />

            <MetricCard
              label="TBT"
              value={
                cws.tbt_ms
                  ? Math.round(cws.tbt_ms)
                  : null
              }
              unit="ms"
              status={metricStatus(
                cws.tbt_ms,
                200,
                600
              )}
            />

            <MetricCard
              label="FCP"
              value={
                cws.fcp_ms
                  ? Math.round(cws.fcp_ms)
                  : null
              }
              unit="ms"
              status={metricStatus(
                cws.fcp_ms,
                1800,
                3000
              )}
            />

            <MetricCard
              label="Bandwidth"
              value={
                cws.total_bytes
                  ? (
                      cws.total_bytes /
                      1_000_000
                    ).toFixed(1)
                  : null
              }
              unit="MB"
              status={metricStatus(
                cws.total_bytes,
                1_800_000,
                3_000_000
              )}
            />
          </div>
        )}

      {!error && !loading && results && items.length === 0 && (
        <div className="mt-6 border border-border bg-panel rounded p-4">
          <div className="text-sm font-medium text-text">
            {note && note.toLowerCase().includes("root cause")
              ? "Root cause not established"
              : "No actionable improvements identified"}
          </div>
          <p className="text-sm text-subtext mt-1.5 leading-relaxed">
            {note ||
              "PageSpeed evidence for this run did not establish a specific, evidence-backed root cause. " +
                "No recommendation was generated rather than guessing."}
          </p>
        </div>
      )}

      {items.length > 0 && (
        <div className="mt-6 space-y-3">
          <h2 className="text-sm font-medium text-subtext">
            Top {items.length} issues, ranked by impact
          </h2>

          {items.map((item, i) => (
            <RecommendationCard
              key={i}
              item={item}
            />
          ))}
        </div>
      )}
    </>
  );
}

// -----------------------------------------------------------------------------
// Monitoring URLs Panel
// -----------------------------------------------------------------------------

function MonitoringUrlsPanel({
  urls,
  onAnalyze,
  onRefresh,
  loading,
}: {
  urls: MonitoringUrl[];
  onAnalyze: (url: string) => void;
  onRefresh: () => void;
  loading: boolean;
}) {
  const grouped = urls.reduce<
    Record<string, MonitoringUrl[]>
  >((groups, item) => {
    const brand = item.brand || "Other";

    if (!groups[brand]) {
      groups[brand] = [];
    }

    groups[brand].push(item);

    return groups;
  }, {});

  if (urls.length === 0) {
    return (
      <div className="mt-5 border border-border rounded-lg bg-panel p-5">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-subtext">
            No enabled monitoring URLs were found
            in the Google Sheet.
          </p>

          <button
            onClick={onRefresh}
            disabled={loading}
            className="text-xs text-subtext hover:text-accent underline underline-offset-2 disabled:opacity-50"
          >
            Refresh
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-5 border border-border rounded-lg bg-panel p-5">
      <div className="flex items-center justify-between gap-3 mb-5">
        <div>
          <h2 className="text-sm font-semibold">
            📊 Monitoring URLs
          </h2>

          <p className="text-xs text-subtext mt-1">
            {urls.length} enabled URL
            {urls.length === 1 ? "" : "s"} from
            Google Apps Script.
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={loading}
          className="px-3 py-1.5 rounded text-xs font-medium border border-border hover:border-accent disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="space-y-6">
        {Object.entries(grouped).map(
          ([brand, brandUrls]) => (
            <section key={brand}>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-subtext mb-3">
                {brand}
              </h3>

              <div className="space-y-3">
                {brandUrls.map(
                  (item, index) => (
                    <div
                      key={`${item.url}-${index}`}
                      className="border border-border rounded-lg p-4 hover:border-accent/50 transition-colors"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium">
                              {item.url_type}
                            </span>

                            <span className="text-[10px] px-2 py-0.5 rounded-full border border-border text-subtext">
                              Monitoring
                            </span>
                          </div>

                          <div className="text-xs text-subtext mt-1 break-all">
                            {item.url}
                          </div>
                        </div>

                        <button
                          onClick={() =>
                            onAnalyze(item.url)
                          }
                          className="px-3.5 py-2 rounded text-sm font-medium bg-accent text-white hover:bg-accent/90 whitespace-nowrap"
                        >
                          Analyze
                        </button>
                      </div>
                    </div>
                  )
                )}
              </div>
            </section>
          )
        )}
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Quick Analyze
// -----------------------------------------------------------------------------

function QuickAnalyzeInner() {
  const searchParams = useSearchParams();

  const prefillUrl =
    searchParams.get("url") || "";

  const [mode, setMode] =
    useState<"url" | "json">("url");

  const [urlInput, setUrlInput] =
    useState(prefillUrl);

  const [jsonInput, setJsonInput] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [note, setNote] =
    useState<string | null>(null);

  const [results, setResults] =
    useState<QuickAnalyzeResult | null>(null);

  const [modelName, setModelName] =
    useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Monitoring URL State
  // ---------------------------------------------------------------------------

  const [monitoringUrls, setMonitoringUrls] =
    useState<MonitoringUrl[]>([]);

  const [loadingMonitoringUrls, setLoadingMonitoringUrls] =
    useState(false);

  const [monitoringError, setMonitoringError] =
    useState<string | null>(null);

  const [showMonitoringUrls, setShowMonitoringUrls] =
    useState(false);

  // ---------------------------------------------------------------------------
  // Analysis
  // ---------------------------------------------------------------------------

  async function runAnalysis(
    fn: () => Promise<QuickAnalyzeResult>
  ) {
    setError(null);
    setNote(null);
    setResults(null);
    setModelName(null);
    setLoading(true);

    try {
      const res = await fn();

      setResults(res);
      setModelName(res.model_name);

      if (res.recommendations.length === 0) {
        setNote(
          res.note ||
            "No issues surfaced - metrics may already be healthy."
        );
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not complete this analysis."
      );
    } finally {
      setLoading(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Google Apps Script Monitoring URLs
  // ---------------------------------------------------------------------------

  async function handleLoadMonitoringUrls() {
    setMonitoringError(null);
    setLoadingMonitoringUrls(true);

    try {
      const response =
        await api.getMonitoringUrls();

      setMonitoringUrls(response.urls);
      setShowMonitoringUrls(true);
    } catch (err) {
      setMonitoringError(
        err instanceof ApiError
          ? err.message
          : "Could not load monitoring URLs."
      );
    } finally {
      setLoadingMonitoringUrls(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Analyze Monitoring URL
  // ---------------------------------------------------------------------------

  async function handleAnalyzeMonitoringUrl(
    url: string
  ) {
    setUrlInput(url);
    setMode("url");
    setShowMonitoringUrls(false);

    await runAnalysis(() =>
      api.quickAnalyzeUrl(url)
    );
  }

  // ---------------------------------------------------------------------------
  // Manual URL Analysis
  // ---------------------------------------------------------------------------

  async function handleRunUrl() {
    if (!urlInput.trim()) {
      return;
    }

    await runAnalysis(() =>
      api.quickAnalyzeUrl(
        urlInput.trim()
      )
    );
  }

  // ---------------------------------------------------------------------------
  // JSON Analysis
  // ---------------------------------------------------------------------------

  async function handleAnalyzeJson() {
    let parsed: unknown;

    try {
      parsed = JSON.parse(jsonInput);
    } catch {
      setError(
        "That doesn't look like valid JSON. Paste the full PageSpeed Insights / Lighthouse report."
      );

      return;
    }

    await runAnalysis(() =>
      api.quickAnalyze(parsed)
    );
  }

  // ---------------------------------------------------------------------------
  // Deep-link support: ?url=...
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (prefillUrl) {
      handleRunUrl();
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------------------------------------------------------------------------
  // UI
  // ---------------------------------------------------------------------------

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold">
          Perf Intelligence
        </h1>

        <p className="text-sm text-subtext mt-1">
          Analyze any webpage - paste a URL
          and run PageSpeed, no setup required.
        </p>
      </header>

      {mode === "url" ? (
        <>
          {/* URL Input */}
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              value={urlInput}
              onChange={(e) =>
                setUrlInput(e.target.value)
              }
              placeholder="https://www.deccanherald.com/..."
              className="flex-1 bg-panel border border-border rounded px-3 py-2 text-sm outline-none focus:border-accent"
            />

            <button
              onClick={handleRunUrl}
              disabled={
                loading ||
                !urlInput.trim()
              }
              className="px-3.5 py-2 rounded text-sm font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {loading
                ? "Running PageSpeed..."
                : "Run PageSpeed"}
            </button>
          </div>

          {/* Raw JSON */}
          <button
            onClick={() => setMode("json")}
            className="text-xs text-subtext hover:text-accent mt-3 underline underline-offset-2"
          >
            Have a raw PageSpeed/Lighthouse
            JSON report instead? Paste it here.
          </button>

          {/* Monitoring URLs */}
          <div className="mt-6 border-t border-border pt-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold">
                  Monitoring URLs
                </h2>

                <p className="text-xs text-subtext mt-1">
                  Load URLs configured in the
                  Google Apps Script monitoring
                  sheet.
                </p>
              </div>

              <button
                onClick={
                  handleLoadMonitoringUrls
                }
                disabled={
                  loadingMonitoringUrls
                }
                className="px-3.5 py-2 rounded text-sm font-medium border border-border bg-panel hover:border-accent disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {loadingMonitoringUrls
                  ? "Loading..."
                  : "📊 Load Monitoring URLs"}
              </button>
            </div>

            {/* Monitoring API Error */}
            {monitoringError && (
              <div className="mt-4 border border-crit/40 bg-crit/5 text-crit rounded p-4 text-sm">
                {monitoringError}
              </div>
            )}

            {/* Monitoring URL Cards */}
            {showMonitoringUrls && (
              <MonitoringUrlsPanel
                urls={monitoringUrls}
                loading={
                  loadingMonitoringUrls
                }
                onRefresh={
                  handleLoadMonitoringUrls
                }
                onAnalyze={
                  handleAnalyzeMonitoringUrl
                }
              />
            )}
          </div>
        </>
      ) : (
        <>
          {/* JSON Input */}
          <textarea
            value={jsonInput}
            onChange={(e) =>
              setJsonInput(e.target.value)
            }
            placeholder='Paste the full report JSON here, e.g. { "lighthouseResult": { ... } }'
            rows={12}
            className="w-full bg-panel border border-border rounded px-3 py-2 text-xs font-mono-num outline-none focus:border-accent resize-y"
          />

          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={handleAnalyzeJson}
              disabled={
                loading ||
                !jsonInput.trim()
              }
              className="px-3.5 py-2 rounded text-sm font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading
                ? "Analyzing..."
                : "Analyze report"}
            </button>

            <button
              onClick={() => setMode("url")}
              className="text-xs text-subtext hover:text-accent underline underline-offset-2"
            >
              Back to paste-a-URL
            </button>
          </div>
        </>
      )}

      {/* Results */}
      <ResultsPanel
        loading={loading}
        error={error}
        note={note}
        results={results}
        modelName={modelName}
      />
    </div>
  );
}

// -----------------------------------------------------------------------------
// Page
// -----------------------------------------------------------------------------

export default function QuickAnalyzePage() {
  return (
    <Suspense fallback={null}>
      <QuickAnalyzeInner />
    </Suspense>
  );
}