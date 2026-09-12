import { Overview } from "@/components/views/Overview";
import { getDashboard } from "@/lib/data";

export default async function Page() {
  const data = await getDashboard();
  return <Overview data={data} />;
}
