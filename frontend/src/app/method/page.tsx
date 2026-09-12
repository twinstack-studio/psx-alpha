import { Method } from "@/components/views/Method";
import { getDashboard } from "@/lib/data";

export const metadata = { title: "Method" };

export default async function Page() {
  const data = await getDashboard();
  return <Method data={data} />;
}
