import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { UserProvider } from "@/lib/user-context";

// Every page after login: the sidebar shell and the logged-in user.
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <UserProvider>
      <AppShell>{children}</AppShell>
    </UserProvider>
  );
}
