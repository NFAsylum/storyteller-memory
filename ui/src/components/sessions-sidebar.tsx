"use client";

import Link from "next/link";

import { ScrollArea } from "@/components/ui/scroll-area";
import { useSessions } from "@/lib/hooks";
import { cn } from "@/lib/utils";

import { SetupWizard } from "./setup-wizard";
import { ThemeToggle } from "./theme-toggle";

export function SessionsSidebar({ activeId }: { activeId: string | null }) {
  const { data: sessions, isLoading } = useSessions();

  return (
    <aside className="w-72 shrink-0 border-r flex flex-col h-full">
      <div className="p-3 border-b flex items-center justify-between gap-2">
        <h2 className="font-semibold text-sm">Sessões</h2>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <SetupWizard />
        </div>
      </div>
      <ScrollArea className="flex-1">
        <nav className="p-2 space-y-1">
          {isLoading && <p className="p-2 text-xs text-muted-foreground">Carregando…</p>}
          {sessions?.length === 0 && (
            <p className="p-2 text-xs text-muted-foreground">Nenhuma sessão ainda.</p>
          )}
          {sessions?.map((s) => (
            <Link
              key={s.id}
              href={`/sessions/${s.id}`}
              data-testid="session-item"
              className={cn(
                "block rounded-md px-3 py-2 text-sm hover:bg-accent",
                activeId === s.id && "bg-accent font-medium",
              )}
            >
              <div className="truncate">{s.name}</div>
              <div className="text-xs text-muted-foreground">
                turno {s.last_turn} · {new Date(s.created_at).toLocaleDateString("pt-BR")}
              </div>
            </Link>
          ))}
        </nav>
      </ScrollArea>
    </aside>
  );
}
