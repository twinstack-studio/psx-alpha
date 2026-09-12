import { notFound } from "next/navigation";

import { Company } from "@/components/views/Company";
import { getCompany, getDashboard, listTickers } from "@/lib/data";

export async function generateStaticParams() {
  const tickers = await listTickers();
  return tickers.map((ticker) => ({ ticker }));
}

export async function generateMetadata({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  const detail = await getCompany(ticker);
  if (!detail) return { title: ticker.toUpperCase() };
  return {
    title: `${detail.ticker} — ${detail.name}`,
    description: detail.explanation?.headline,
  };
}

export default async function Page({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  const [detail, data] = await Promise.all([getCompany(ticker), getDashboard()]);
  const row = data.recommendations.find(
    (r) => r.ticker.toUpperCase() === ticker.toUpperCase(),
  );
  if (!detail || !row) notFound();
  return <Company detail={detail} row={row} universeSize={data.meta.universeSize} />;
}
