import { Screener } from "@/components/views/Screener";
import { getDashboard } from "@/lib/data";

export const metadata = { title: "Screener" };

export default async function Page() {
  const data = await getDashboard();
  return <Screener data={data} />;
}
