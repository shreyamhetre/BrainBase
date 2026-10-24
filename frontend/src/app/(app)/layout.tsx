import { Suspense, type ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { UserProvider } from "@/lib/user-context";

// Every page after login: the sidebar shell and the logged-in user. The shell reads the
// current address, so it sits in a Suspense boundary (required for pages like /c/<id>).
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <UserProvider>
      <Suspense fallback={<div className="flex-1" />}>
        <AppShell>{children}</AppShell>
      </Suspense>
    </UserProvider>
  );
}
