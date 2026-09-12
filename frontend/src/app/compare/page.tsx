import { Compare } from "@/components/views/Compare";
import { getDashboard } from "@/lib/data";

export const metadata = {
  title: "Compare",
  description: "Put up to four KSE-100 names on the same axes: pillar profiles, rebased price paths and a metric-by-metric scoreboard.",
};

export default async function Page() {
  const data = await getDashboard();
  return <Compare data={data} />;
}
