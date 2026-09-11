import Link from "next/link";
import { api } from "@/lib/api";

export default async function RunsPickerPage() {
  const sites = await api.listSites().catch(() => []);
  const groups = await Promise.all(
    sites.map(async (site) => ({
      site,
      urls: await api.listUrls(site.site_id),
    }))
  );

  const rows = await Promise.all(
    groups.flatMap((g) =>
      g.urls.map(async (u) => {
        const runs = await api.listRuns(u.url_id).catch(() => []);
        return { site: g.site, url: u, latest: runs[0] || null, count: runs.length };
      })
    )
  );

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Runs</h1>
        <p className="text-sm text-subtext mt-1">Latest PSI run status per monitored URL.</p>
      </header>

      <div className="border border-border rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-panel2 text-left text-xs text-subtext">
              <th className="px-4 py-2.5 font-medium">Site</th>
              <th className="px-4 py-2.5 font-medium">URL</th>
              <th className="px-4 py-2.5 font-medium">Latest run</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Total runs</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ site, url, latest, count }) => (
              <tr key={url.url_id} className="border-t border-border hover:bg-panel/60">
                <td className="px-4 py-3 text-subtext">{site.name}</td>
                <td className="px-4 py-3">
                  <Link href={`/urls/${url.url_id}`} className="hover:text-accent truncate block max-w-sm">
                    {url.url}
                  </Link>
                </td>
                <td className="px-4 py-3 text-subtext">{latest ? new Date(latest.run_timestamp).toLocaleString() : "—"}</td>
                <td className="px-4 py-3">
                  {latest ? (
                    <span
                      className={`text-xs px-2 py-0.5 rounded border ${
                        latest.run_status === "success" ? "text-good border-good/40 bg-good/10" : "text-crit border-crit/40 bg-crit/10"
                      }`}
                    >
                      {latest.run_status}
                    </span>
                  ) : (
                    <span className="text-subtext text-xs">No runs yet</span>
                  )}
                </td>
                <td className="px-4 py-3 font-mono-num">{count}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-subtext">
                  No URLs configured yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
