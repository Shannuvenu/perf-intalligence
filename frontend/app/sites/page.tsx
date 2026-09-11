import Link from "next/link";
import { Globe2 } from "lucide-react";
import { api } from "@/lib/api";
import AddSiteForm from "@/components/AddSiteForm";

export default async function SitesPage() {
  const sites = await api.listSites().catch(() => []);

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Sites</h1>
        <p className="text-sm text-subtext mt-1">Multi-tenant by site — each site&apos;s URLs and history stay isolated.</p>
      </header>

      <div className="border border-border rounded overflow-hidden mb-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-panel2 text-left text-xs text-subtext">
              <th className="px-4 py-2.5 font-medium">Site</th>
              <th className="px-4 py-2.5 font-medium">Base URL</th>
              <th className="px-4 py-2.5 font-medium">URLs</th>
              <th className="px-4 py-2.5 font-medium">Added</th>
            </tr>
          </thead>
          <tbody>
            {sites.map((site) => (
              <tr key={site.site_id} className="border-t border-border hover:bg-panel/60">
                <td className="px-4 py-3">
                  <Link href={`/sites/${site.site_id}`} className="flex items-center gap-2 font-medium hover:text-accent">
                    <Globe2 size={14} className="text-subtext" />
                    {site.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-subtext">{site.base_url}</td>
                <td className="px-4 py-3 font-mono-num">{site.url_count}</td>
                <td className="px-4 py-3 text-subtext">{new Date(site.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
            {sites.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-subtext">
                  No sites yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <AddSiteForm />
    </div>
  );
}
