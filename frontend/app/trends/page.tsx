import Link from "next/link";
import { TrendingUp } from "lucide-react";
import { api } from "@/lib/api";

export default async function TrendsPickerPage() {
  const sites = await api.listSites().catch(() => []);
  const groups = await Promise.all(sites.map(async (site) => ({ site, urls: await api.listUrls(site.site_id) })));

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Trends</h1>
        <p className="text-sm text-subtext mt-1">Select a URL to see how its metrics have moved over time.</p>
      </header>

      <div className="space-y-6">
        {groups.map(({ site, urls }) => (
          <div key={site.site_id}>
            <p className="text-xs text-subtext mb-2">{site.name}</p>
            <div className="space-y-2">
              {urls.map((u) => (
                <Link
                  key={u.url_id}
                  href={`/urls/${u.url_id}/trends`}
                  className="flex items-center justify-between gap-3 border border-border bg-panel rounded px-4 py-3 hover:border-accent/60 transition-colors"
                >
                  <span className="text-sm truncate">{u.url}</span>
                  <TrendingUp size={14} className="text-subtext shrink-0" />
                </Link>
              ))}
            </div>
          </div>
        ))}
        {groups.length === 0 && <div className="border border-border bg-panel rounded p-8 text-center text-subtext">No URLs configured yet.</div>}
      </div>
    </div>
  );
}
