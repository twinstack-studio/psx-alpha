import { Watchlist } from "@/components/views/Watchlist";
import { getDashboard } from "@/lib/data";

export const metadata = {
  title: "Watchlist",
  description: "The names you starred, scored by the engine and kept in this browser.",
};

export default async function Page() {
  const data = await getDashboard();
  return <Watchlist data={data} />;
}
