import Link from "next/link";
import { Globe2 } from "lucide-react";
import { api } from "@/lib/api";
import AddSiteForm from "@/components/AddSiteForm";

export default async function OverviewPage() {
  const sites = await api.listSites().catch(() => []);

  return (
    <div>
      <header className="mb-8">
        <h1 className="text-xl font-semibold">Overview</h1>
        <p className="text-sm text-subtext mt-1">
          Performance &amp; accessibility intelligence across your monitored sites.
        </p>
      </header>

      {sites.length === 0 ? (
        <div className="border border-border bg-panel rounded p-8 text-center max-w-md mx-auto mt-16">
          <Globe2 size={22} className="text-subtext mx-auto mb-3" />
          <p className="text-sm text-subtext mb-4">
            No sites yet. Add Deccan Herald or Prajavani, or run <code className="font-mono-num">python -m app.seed_demo</code> for sample data.
          </p>
          <AddSiteForm />
        </div>
      ) : (
        <div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            {sites.map((site) => (
              <Link
                key={site.site_id}
                href={`/sites/${site.site_id}`}
                className="border border-border bg-panel rounded p-5 hover:border-accent/60 transition-colors"
              >
                <div className="flex items-center gap-2 mb-1">
                  <Globe2 size={15} className="text-accent" />
                  <span className="font-medium text-sm">{site.name}</span>
                </div>
                <p className="text-xs text-subtext truncate mb-3">{site.base_url}</p>
                <p className="text-xs text-subtext">
                  <span className="font-mono-num text-text">{site.url_count}</span> monitored URL
                  {site.url_count === 1 ? "" : "s"}
                </p>
              </Link>
            ))}
          </div>
          <AddSiteForm />
        </div>
      )}
    </div>
  );
}
