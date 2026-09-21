import Link from "next/link";
import { api } from "@/lib/api";
import MetricCard from "@/components/MetricCard";
import ValidationBadge from "@/components/ValidationBadge";
import RecommendationCard from "@/components/RecommendationCard";
import RunAnalyzeControls from "./RunAnalyzeControls";

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

export default async function UrlDetailPage({ params }: { params: { urlId: string } }) {
  const urlId = Number(params.urlId);

  const [url, runs, stabilized, recommendations, strengthsRes] = await Promise.all([
    api.getUrl(urlId),
    api.listRuns(urlId),
    api.getStabilized(urlId).catch(() => null),
    api.listRecommendations(urlId).catch(() => []),
    api.getStrengths(urlId).catch(() => ({ url_id: urlId, strengths: [] })),
  ]);

  const site = await api.getSite(url.site_id);
  const latestRec = recommendations[0];
  const strengths = strengthsRes.strengths;
  const m = stabilized?.median_metrics || {};

  return (
    <div>
      <header className="mb-6">
        <p className="text-xs text-subtext mb-1">
          <Link href="/sites" className="hover:text-accent">
            Sites
          </Link>{" "}
          /{" "}
          <Link href={`/sites/${site.site_id}`} className="hover:text-accent">
            {site.name}
          </Link>
        </p>
        <h1 className="text-lg font-semibold break-all">{url.url}</h1>
        <p className="text-sm text-subtext mt-1 capitalize">{url.url_category} page</p>
      </header>

      <RunAnalyzeControls urlId={urlId} runCount={runs.length} />

      {!stabilized ? (
        <div className="border border-border bg-panel rounded p-6 mt-6 text-sm text-subtext">
          Not enough successful runs yet to stabilize metrics. Run PageSpeed a few more times (minimum 3 runs), then
          click Stabilize.
          <span className="block mt-1 font-mono-num">{runs.length} run(s) recorded so far.</span>
        </div>
      ) : (
        <>
          <section className="mt-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-subtext">
                Stabilized metrics{" "}
                <span className="font-mono-num text-text">· median of {stabilized.run_count} runs</span>
              </h2>
              {stabilized.flagged && (
                <span className="text-xs px-2 py-0.5 rounded border text-warn border-warn/40 bg-warn/10">
                  High variability - treat with caution
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
              <MetricCard label="Performance" value={m.performance_score} status={metricStatus(m.performance_score, 90, 50, false)} />
              <MetricCard label="Accessibility" value={m.accessibility_score} status={metricStatus(m.accessibility_score, 90, 70, false)} />
              <MetricCard label="LCP" value={m.lcp_ms ? Math.round(m.lcp_ms) : null} unit="ms" status={metricStatus(m.lcp_ms, 2500, 4000)} />
              <MetricCard label="CLS" value={m.cls} status={metricStatus(m.cls, 0.1, 0.25)} />
              <MetricCard label="TBT" value={m.tbt_ms ? Math.round(m.tbt_ms) : null} unit="ms" status={metricStatus(m.tbt_ms, 200, 600)} />
              <MetricCard label="FCP" value={m.fcp_ms ? Math.round(m.fcp_ms) : null} unit="ms" status={metricStatus(m.fcp_ms, 1800, 3000)} />
              <MetricCard
                label="Bandwidth"
                value={m.total_bytes ? (m.total_bytes / 1_000_000).toFixed(1) : null}
                unit="MB"
                status={metricStatus(m.total_bytes, 1_800_000, 3_000_000)}
              />
            </div>
          </section>

          <section className="mt-8">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-subtext">Top recommended fixes</h2>
              <div className="flex items-center gap-2">
                {latestRec && <ValidationBadge status={latestRec.validation_status} />}
              </div>
            </div>

            {!latestRec ? (
              <div className="border border-border bg-panel rounded p-6 text-sm text-subtext">
                No recommendations generated yet. Click Analyze above.
              </div>
            ) : latestRec.root_cause_groups.length === 0 ? (
              <div
                className={`border rounded p-6 text-sm ${
                  latestRec.validation_status === "invalid"
                    ? "border-crit/40 bg-crit/5 text-crit"
                    : "border-border bg-panel text-subtext"
                }`}
              >
                {latestRec.insufficient_evidence_note ||
                  "No root causes surfaced from the current evidence — metrics may already be within healthy thresholds."}
              </div>
            ) : (
              <div className="space-y-3">
                {latestRec.root_cause_groups.map((item, i) => (
                  <RecommendationCard key={i} item={item} />
                ))}
              </div>
            )}
            {latestRec && (
              <p className="text-xs text-subtext mt-3">
                Generated {new Date(latestRec.generated_at).toLocaleString()} by{" "}
                <span className="font-mono-num">{latestRec.model_name}</span> from runs{" "}
                <span className="font-mono-num">{latestRec.source_run_ids.join(", ")}</span>.
              </p>
            )}
          </section>

          {strengths.length > 0 && (
            <section className="mt-8">
              <h2 className="text-sm font-medium text-subtext mb-3">
                What this page is doing well
                <span className="text-xs text-subtext font-normal ml-2">
                  — useful when benchmarking against a competitor site
                </span>
              </h2>
              <div className="border border-good/30 bg-good/5 rounded p-4">
                <ul className="space-y-2">
                  {strengths.map((s, i) => (
                    <li key={i} className="text-sm leading-relaxed flex gap-2.5">
                      <span className="text-good shrink-0 mt-0.5">✓</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}
        </>
      )}

      <section className="mt-8">
        <h2 className="text-sm font-medium text-subtext mb-3">Recent runs</h2>
        <div className="border border-border rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-panel2 text-left text-xs text-subtext">
                <th className="px-4 py-2.5 font-medium">Run</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Performance</th>
                <th className="px-4 py-2.5 font-medium">Accessibility</th>
                <th className="px-4 py-2.5 font-medium">LCP</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 10).map((r) => (
                <tr key={r.run_id} className="border-t border-border">
                  <td className="px-4 py-2.5 text-subtext">{new Date(r.run_timestamp).toLocaleString()}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`text-xs px-2 py-0.5 rounded border ${
                        r.run_status === "success" ? "text-good border-good/40 bg-good/10" : "text-crit border-crit/40 bg-crit/10"
                      }`}
                    >
                      {r.run_status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono-num">{r.category_scores.performance ?? "—"}</td>
                  <td className="px-4 py-2.5 font-mono-num">{r.category_scores.accessibility ?? "—"}</td>
                  <td className="px-4 py-2.5 font-mono-num">{r.core_web_vitals.lcp_ms ? Math.round(r.core_web_vitals.lcp_ms) + "ms" : "—"}</td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-subtext">
                    No runs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
