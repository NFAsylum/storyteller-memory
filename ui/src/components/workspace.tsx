"use client";

import { ChatArea } from "./chat-area";
import { DebugPanel } from "./debug-panel";
import { MemoryInspector } from "./memory-inspector";
import { SessionsSidebar } from "./sessions-sidebar";

export function Workspace({ activeId }: { activeId: string | null }) {
  return (
    <div className="flex h-screen w-full">
      <SessionsSidebar activeId={activeId} />
      {activeId ? (
        <>
          <ChatArea sessionId={activeId} />
          <aside className="w-96 shrink-0 border-l flex flex-col h-full">
            <div className="min-h-0 flex-1">
              <MemoryInspector sessionId={activeId} />
            </div>
            <DebugPanel sessionId={activeId} />
          </aside>
        </>
      ) : (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Crie ou selecione uma sessão à esquerda.
        </div>
      )}
    </div>
  );
}
