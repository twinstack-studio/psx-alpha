import { Model } from "@/components/views/Model";
import { getDashboard } from "@/lib/data";

export const metadata = { title: "Model diagnostics" };

export default async function Page() {
  const data = await getDashboard();
  return <Model data={data} />;
}
