import { Suspense } from "react";
import { Chat } from "@/components/chat";

// A saved chat, reopened from the sidebar. The id comes from the address, read on the server.
export default function SavedChatPage({ params }: PageProps<"/c/[id]">) {
  return (
    <Suspense fallback={<main className="flex-1" />}>
      <SavedChat params={params} />
    </Suspense>
  );
}

async function SavedChat({ params }: { params: PageProps<"/c/[id]">["params"] }) {
  const { id } = await params;
  return <Chat key={id} conversationId={id} />;
}
