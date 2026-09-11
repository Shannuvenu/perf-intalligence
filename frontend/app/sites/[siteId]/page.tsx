import Link from "next/link";
import { FileText, Home as HomeIcon } from "lucide-react";
import { api } from "@/lib/api";
import AddUrlForm from "@/components/AddUrlForm";

const CATEGORY_ICON: Record<string, typeof FileText> = {
  homepage: HomeIcon,
  article: FileText,
};

export default async function SiteUrlsPage({ params }: { params: { siteId: string } }) {
  const siteId = Number(params.siteId);
  const [site, urls] = await Promise.all([api.getSite(siteId), api.listUrls(siteId)]);

  return (
    <div>
      <header className="mb-6">
        <p className="text-xs text-subtext mb-1">
          <Link href="/sites" className="hover:text-accent">
            Sites
          </Link>{" "}
          / {site.name}
        </p>
        <h1 className="text-xl font-semibold">{site.name}</h1>
        <p className="text-sm text-subtext mt-1">{site.base_url}</p>
      </header>

      <div className="border border-border rounded overflow-hidden mb-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-panel2 text-left text-xs text-subtext">
              <th className="px-4 py-2.5 font-medium">URL</th>
              <th className="px-4 py-2.5 font-medium">Category</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {urls.map((u) => {
              const Icon = CATEGORY_ICON[u.url_category] || FileText;
              return (
                <tr key={u.url_id} className="border-t border-border hover:bg-panel/60">
                  <td className="px-4 py-3">
                    <Link href={`/urls/${u.url_id}`} className="flex items-center gap-2 hover:text-accent">
                      <Icon size={14} className="text-subtext shrink-0" />
                      <span className="truncate max-w-md">{u.url}</span>
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-subtext capitalize">{u.url_category}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded border ${u.enabled ? "text-good border-good/40 bg-good/10" : "text-subtext border-border"}`}>
                      {u.enabled ? "Enabled" : "Disabled"}
                    </span>
                  </td>
                </tr>
              );
            })}
            {urls.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-subtext">
                  No URLs yet for this site.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <AddUrlForm siteId={siteId} />
    </div>
  );
}
