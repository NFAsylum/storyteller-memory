"use client";

import { PanelLeft, PanelRight } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

import { ChatArea } from "./chat-area";
import { DebugPanel } from "./debug-panel";
import { MemoryInspector } from "./memory-inspector";
import { SessionsSidebar } from "./sessions-sidebar";

// Shell colapsável: sessões (esquerda) e memória (direita) podem ser fechadas em
// QUALQUER tamanho de tela — a coluna central (história) ocupa o resto. Altura fixa
// (h-screen + overflow-hidden); só a lista de turnos rola, os painéis ficam parados.
export function Workspace({
  activeId,
  initialInput,
}: {
  activeId: string | null;
  initialInput?: string;
}) {
  const [showSidebar, setShowSidebar] = useState(true);
  const [showInspector, setShowInspector] = useState(true);

  // Começa colapsado em telas estreitas pra a coluna central não ser esmagada.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.innerWidth < 1024) setShowSidebar(false);
    if (window.innerWidth < 1280) setShowInspector(false);
  }, []);

  return (
    <div className="flex h-screen w-full overflow-hidden">
      {showSidebar && <SessionsSidebar activeId={activeId} />}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex shrink-0 items-center gap-1 border-b px-1.5 py-1">
          <Button
            variant="ghost"
            size="sm"
            className="size-7 p-0"
            aria-label={showSidebar ? "esconder sessões" : "mostrar sessões"}
            aria-pressed={showSidebar}
            onClick={() => setShowSidebar((v) => !v)}
          >
            <PanelLeft className="size-4" />
          </Button>
          <span className="flex-1" />
          {activeId && (
            <Button
              variant="ghost"
              size="sm"
              className="size-7 p-0"
              aria-label={showInspector ? "esconder memória" : "mostrar memória"}
              aria-pressed={showInspector}
              onClick={() => setShowInspector((v) => !v)}
            >
              <PanelRight className="size-4" />
            </Button>
          )}
        </div>

        <div className="flex min-h-0 flex-1">
          {activeId ? (
            <>
              <ChatArea sessionId={activeId} initialInput={initialInput} />
              {showInspector && (
                <aside className="flex h-full w-96 shrink-0 flex-col border-l">
                  <div className="min-h-0 flex-1">
                    <MemoryInspector sessionId={activeId} />
                  </div>
                  <DebugPanel sessionId={activeId} />
                </aside>
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
