import Link from "next/link";
import { api } from "@/lib/api";
import TrendChart from "@/components/TrendChart";

export default async function UrlTrendsPage({ params }: { params: { urlId: string } }) {
  const urlId = Number(params.urlId);
  const [url, trends] = await Promise.all([api.getUrl(urlId), api.getTrends(urlId)]);
  const site = await api.getSite(url.site_id);

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
          </Link>{" "}
          /{" "}
          <Link href={`/urls/${urlId}`} className="hover:text-accent">
            URL
          </Link>
        </p>
        <h1 className="text-lg font-semibold break-all">Trends</h1>
        <p className="text-sm text-subtext mt-1 break-all">{url.url}</p>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {trends.metrics.map((trend) => (
          <TrendChart key={trend.metric} trend={trend} />
        ))}
      </div>
    </div>
  );
}
