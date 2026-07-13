"use client";

import { useState } from "react";
import { toast } from "sonner";
import { mutate } from "swr";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useSession } from "@/lib/hooks";

import { SessionConfigChip } from "./session-config-chip";

export function ChatArea({
  sessionId,
  initialInput,
}: {
  sessionId: string;
  initialInput?: string;
}) {
  const { data: session, isLoading } = useSession(sessionId);
  const [text, setText] = useState(initialInput ?? "");
  const [busy, setBusy] = useState(false);

  async function send() {
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    try {
      await api.runTurn(sessionId, value);
      setText("");
      await Promise.all([
        mutate(`session:${sessionId}`),
        mutate(`state:${sessionId}`),
        mutate("sessions"),
      ]);
    } catch (err) {
      toast.error(`Erro no turno: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex-1 flex flex-col h-full min-w-0">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <span className="truncate text-sm font-medium">{session?.name ?? "…"}</span>
        <SessionConfigChip sessionId={sessionId} />
      </div>
      <ScrollArea className="flex-1 p-4">
        <div className="mx-auto max-w-2xl space-y-4">
          {isLoading && <Skeleton className="h-24 w-full" />}
          {session?.turns.map((t) => (
            <div key={t.turn_number} data-testid="turn" className="space-y-2">
              <p className="text-sm">
                <span className="font-semibold">Você:</span> {t.user_input}
              </p>
              <p className="rounded-md bg-muted p-3 text-sm">
                <span className="font-semibold">Narrador:</span> {t.narrator_text}
              </p>
            </div>
          ))}
          {busy && (
            <p className="text-sm text-muted-foreground animate-pulse">Continuando a história…</p>
          )}
          {session && session.turns.length === 0 && !busy && (
            <p className="text-sm text-muted-foreground">Escreva o primeiro turno abaixo.</p>
          )}
        </div>
      </ScrollArea>
      <div className="border-t p-3 flex gap-2">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="O que acontece agora? (Ctrl+Enter envia)"
          aria-label="entrada do turno"
          className="min-h-10 resize-none"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <Button onClick={send} disabled={busy || !text.trim()}>
          Próximo turno
        </Button>
      </div>
    </section>
  );
}
