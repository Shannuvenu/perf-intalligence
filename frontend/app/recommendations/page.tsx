import Link from "next/link";
import { api } from "@/lib/api";
import PriorityBadge from "@/components/PriorityBadge";
import ValidationBadge from "@/components/ValidationBadge";

export default async function RecommendationsPickerPage() {
  const sites = await api.listSites().catch(() => []);
  const groups = await Promise.all(sites.map(async (site) => ({ site, urls: await api.listUrls(site.site_id) })));

  const rows = await Promise.all(
    groups.flatMap((g) =>
      g.urls.map(async (u) => {
        const recs = await api.listRecommendations(u.url_id).catch(() => []);
        return { site: g.site, url: u, latest: recs[0] || null };
      })
    )
  );

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Recommendations</h1>
        <p className="text-sm text-subtext mt-1">Latest evidence-backed fix list generated per URL.</p>
      </header>

      <div className="space-y-3">
        {rows.map(({ site, url, latest }) => (
          <Link
            key={url.url_id}
            href={`/urls/${url.url_id}`}
            className="block border border-border bg-panel rounded p-4 hover:border-accent/60 transition-colors"
          >
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-xs text-subtext mb-0.5">{site.name}</p>
                <p className="text-sm truncate">{url.url}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {latest ? (
                  <>
                    <PriorityBadge priority={latest.priority_rank} />
                    <ValidationBadge status={latest.validation_status} />
                    <span className="text-xs text-subtext font-mono-num">
                      {latest.root_cause_groups.length} finding{latest.root_cause_groups.length === 1 ? "" : "s"}
                    </span>
                  </>
                ) : (
                  <span className="text-xs text-subtext">Not analyzed yet</span>
                )}
              </div>
            </div>
          </Link>
        ))}
        {rows.length === 0 && <div className="border border-border bg-panel rounded p-8 text-center text-subtext">No URLs configured yet.</div>}
      </div>
    </div>
  );
}
