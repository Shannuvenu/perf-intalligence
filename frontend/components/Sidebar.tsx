"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Gauge, Globe2, LayoutGrid, ListChecks, TrendingUp } from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutGrid },
  { href: "/sites", label: "Sites", icon: Globe2 },
  { href: "/runs", label: "Runs", icon: Activity },
  { href: "/recommendations", label: "Recommendations", icon: ListChecks },
  { href: "/trends", label: "Trends", icon: TrendingUp },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 shrink-0 border-r border-border bg-panel h-screen sticky top-0 flex flex-col">
      <div className="px-5 py-5 border-b border-border">
        <div className="flex items-center gap-2">
          <Gauge size={20} className="text-accent" strokeWidth={2.25} />
          <span className="font-semibold tracking-tight text-[15px]">Perf Intelligence</span>
        </div>
        <p className="text-xs text-subtext mt-1">Deccan Herald &amp; Prajavani</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded text-sm transition-colors ${
                active ? "bg-panel2 text-text" : "text-subtext hover:text-text hover:bg-panel2/60"
              }`}
            >
              <Icon size={16} strokeWidth={2} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4 border-t border-border text-[11px] text-subtext leading-relaxed">
        Evidence-backed fix lists from stabilized, multi-run PSI data.
      </div>
    </aside>
  );
}
