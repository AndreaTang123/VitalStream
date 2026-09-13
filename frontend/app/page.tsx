import { redirect } from "next/navigation";
import { loadUser } from "@/lib/server/loadUser";
import { defaultRouteForRole } from "@/lib/roles";

export default async function RootPage() {
  const user = await loadUser();
  redirect(user ? defaultRouteForRole(user.role) : "/login");
}
