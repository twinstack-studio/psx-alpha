import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AuroraCanvas } from "@/components/AuroraCanvas";
import { Shell } from "@/components/Shell";
import { getDashboard } from "@/lib/data";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: "PSX Alpha — AI Stock Recommendation Engine",
    template: "%s · PSX Alpha",
  },
  description:
    "Scores and ranks KSE-100 companies from financial statements, sector-relative ratios and price data, with a plain-language explanation behind every recommendation.",
};

export const viewport: Viewport = {
  themeColor: "#060710",
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const data = await getDashboard();
  const index = data.recommendations.map((r) => ({
    ticker: r.ticker,
    name: r.name,
    sector: r.sector,
    band: r.recommendation,
    score: r.finalScore,
    rank: r.rank,
  }));

  // The tape carries only what it draws, so the whole cross-section does not
  // have to cross the server/client boundary a second time.
  const ticker = data.recommendations.map((r) => ({
    ticker: r.ticker,
    price: r.price,
    return12m: r.return12m,
    band: r.recommendation,
    spark: r.spark.slice(-24),
  }));

  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <AuroraCanvas />
        <Shell
          asOf={data.meta.asOf}
          universeSize={data.meta.universeSize}
          index={index}
          ticker={ticker}
        >
          {children}
        </Shell>
      </body>
    </html>
  );
}
