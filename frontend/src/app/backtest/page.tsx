import { Backtest } from "@/components/views/Backtest";
import { getDashboard } from "@/lib/data";

export const metadata = { title: "Backtest" };

export default async function Page() {
  const data = await getDashboard();
  return <Backtest data={data} />;
}
