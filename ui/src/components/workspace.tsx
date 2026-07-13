"use client";

import { Menu, PanelRightOpen } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { ChatArea } from "./chat-area";
import { DebugPanel } from "./debug-panel";
import { MemoryInspector } from "./memory-inspector";
import { SessionsSidebar } from "./sessions-sidebar";

// Responsive shell (T6.1): full 3 columns on xl+, sidebar as a drawer below lg, and the
// memory inspector as a drawer below xl. Chat is always the primary column.
export function Workspace({
  activeId,
  initialInput,
}: {
  activeId: string | null;
  initialInput?: string;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  return (
    <div className="flex h-screen w-full overflow-hidden">
      <div
        className={cn(
          "z-40 shrink-0 bg-background lg:static lg:z-auto lg:block",
          sidebarOpen ? "fixed inset-y-0 left-0" : "hidden lg:block",
        )}
      >
        <SessionsSidebar activeId={activeId} />
      </div>
      {sidebarOpen && (
        <div
          data-testid="sidebar-overlay"
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b p-2 xl:hidden">
          <Button
            variant="ghost"
            size="sm"
            className="lg:hidden"
            aria-label="abrir sessões"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="size-4" />
          </Button>
          <span className="flex-1" />
          {activeId && (
            <Button
              variant="ghost"
              size="sm"
              aria-label="abrir memória"
              onClick={() => setInspectorOpen(true)}
            >
              <PanelRightOpen className="size-4" />
            </Button>
          )}
        </div>

        <div className="flex min-h-0 flex-1">
          {activeId ? (
            <>
              <ChatArea sessionId={activeId} initialInput={initialInput} />
              <aside
                className={cn(
                  "z-40 flex h-full flex-col border-l bg-background xl:static xl:z-auto xl:flex xl:w-96",
                  inspectorOpen ? "fixed inset-y-0 right-0 w-80" : "hidden xl:flex",
                )}
              >
                <div className="min-h-0 flex-1">
                  <MemoryInspector sessionId={activeId} />
                </div>
                <DebugPanel sessionId={activeId} />
              </aside>
              {inspectorOpen && (
                <div
                  data-testid="inspector-overlay"
                  className="fixed inset-0 z-30 bg-black/40 xl:hidden"
                  onClick={() => setInspectorOpen(false)}
                />
              )}
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
              Crie ou selecione uma sessão.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
