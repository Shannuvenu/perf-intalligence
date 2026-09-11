import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Perf Intelligence",
  description: "Performance & accessibility intelligence for Deccan Herald and Prajavani.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen bg-bg text-text">
          <Sidebar />
          <main className="flex-1 min-w-0">
            <div className="max-w-6xl mx-auto px-8 py-8">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
