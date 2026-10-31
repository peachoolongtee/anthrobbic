import { redirect } from "next/navigation";

/** The overview moved to the home page; keep old links working. */
export default function DashboardPage() {
  redirect("/");
}
