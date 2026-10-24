"use client";

import { EmptyState } from "@/components/admin/parts";
import { PageHeader } from "@/components/app-shell";
import { useUser } from "@/lib/user-context";

// MCP tools let GitMore act in company tools (create an issue, post a message) after you confirm.
// Connecting servers and choosing which roles may use each tool comes after the connectors.
export default function McpPage() {
  const { user } = useUser();

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
      <PageHeader title="MCP tools"
        description="Actions GitMore can take for you in company tools, such as creating a GitLab issue or posting in Slack. Nothing is written until you confirm." />

      <EmptyState icon="tool" title="No tools connected yet">
        {user?.is_admin
          ? "Connecting the GitLab and Slack MCP servers, turning tools on or off, and choosing which roles may use them come after the connectors."
          : "When your admin connects tools, you'll see them here and which ones you can use."}
      </EmptyState>
    </main>
  );
}
