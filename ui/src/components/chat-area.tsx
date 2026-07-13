"use client";

import { GitFork, Pencil, RefreshCw, Undo2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { mutate } from "swr";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, type Turn } from "@/lib/api";
import { useSession } from "@/lib/hooks";
import { relativeTime } from "@/lib/relative-time";
import { onScrollToTurn } from "@/lib/scroll-to-turn";
import { saveSessionCookie } from "@/lib/session-cookie";

import { ExportDialog } from "./export-dialog";
import { SessionConfigChip } from "./session-config-chip";

function refresh(sessionId: string): Promise<unknown> {
  return Promise.all([
    mutate(`session:${sessionId}`),
    mutate(`state:${sessionId}`),
    mutate("sessions"),
  ]);
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button variant="ghost" size="sm" className="size-6 p-0" aria-label={label} onClick={onClick}>
      {children}
    </Button>
  );
}

function TurnBlock({
  sessionId,
  turn,
  isLast,
}: {
  sessionId: string;
  turn: Turn;
  isLast: boolean;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(turn.user_input);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<unknown>, onDone?: () => void) {
    setBusy(true);
    try {
      await action();
      await refresh(sessionId);
      onDone?.();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function fork() {
    setBusy(true);
    try {
      const forked = await api.forkSession(sessionId, turn.turn_number);
      saveSessionCookie(forked.id);
      await mutate("sessions");
      router.push(`/sessions/${forked.id}`);
    } catch (err) {
      toast.error(`Falha ao forkar: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      id={`turn-${turn.turn_number}`}
      data-testid="turn"
      className={`group space-y-1.5 rounded-lg p-2 ${isLast ? "ring-1 ring-primary/20" : ""}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-muted-foreground">
          turno {turn.turn_number} · {relativeTime(turn.created_at)}
        </span>
        <div className="flex gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
          {!editing && (
            <IconButton label={`editar turno ${turn.turn_number}`} onClick={() => setEditing(true)}>
              <Pencil className="size-3.5" />
            </IconButton>
          )}
          <IconButton
            label={`regenerar turno ${turn.turn_number}`}
            onClick={() => run(() => api.regenerateTurn(sessionId, turn.turn_number))}
          >
            <RefreshCw className="size-3.5" />
          </IconButton>
          <IconButton label={`forkar do turno ${turn.turn_number}`} onClick={fork}>
            <GitFork className="size-3.5" />
          </IconButton>
          {isLast && (
            <IconButton
              label={`desfazer turno ${turn.turn_number}`}
              onClick={() => run(() => api.deleteTurn(sessionId, turn.turn_number))}
            >
              <Undo2 className="size-3.5" />
            </IconButton>
          )}
        </div>
      </div>

      {editing ? (
        <div className="space-y-1.5">
          <Textarea
            aria-label="editar entrada do turno"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="min-h-10 resize-none"
          />
          <div className="flex gap-1.5">
            <Button
              size="sm"
              disabled={busy || !draft.trim()}
              onClick={() =>
                run(() => api.editTurn(sessionId, turn.turn_number, draft.trim()), () =>
                  setEditing(false),
                )
              }
            >
              Salvar e re-narrar
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setDraft(turn.user_input);
                setEditing(false);
              }}
            >
              Cancelar
            </Button>
          </div>
        </div>
      ) : (
        <p className="ml-auto max-w-[85%] rounded-lg bg-primary/10 px-3 py-2 text-sm">
          {turn.user_input}
        </p>
      )}
      <p className="mr-auto max-w-[95%] rounded-lg bg-muted px-3 py-2 text-sm whitespace-pre-wrap">
        {turn.narrator_text}
      </p>
    </div>
  );
}

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
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  const turnCount = session?.turns.length ?? 0;

  useEffect(
    () =>
      onScrollToTurn((turn) => {
        document
          .getElementById(`turn-${turn}`)
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
      }),
    [],
  );

  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turnCount, busy, autoScroll]);

  async function send() {
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    try {
      await api.runTurn(sessionId, value);
      setText("");
      await refresh(sessionId);
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
        <div className="flex shrink-0 items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            aria-pressed={autoScroll}
            onClick={() => setAutoScroll((v) => !v)}
          >
            Auto-scroll: {autoScroll ? "on" : "off"}
          </Button>
          <ExportDialog sessionId={sessionId} />
          <SessionConfigChip sessionId={sessionId} />
        </div>
      </div>
      <ScrollArea className="flex-1 p-4">
        <div className="mx-auto max-w-2xl space-y-3">
          {isLoading && <Skeleton className="h-24 w-full" />}
          {session?.turns.map((t, i) => (
            <TurnBlock
              key={t.turn_number}
              sessionId={sessionId}
              turn={t}
              isLast={i === turnCount - 1}
            />
          ))}
          {busy && (
            <p className="text-sm text-muted-foreground animate-pulse">Continuando a história…</p>
          )}
          {session && turnCount === 0 && !busy && (
            <p className="text-sm text-muted-foreground">Escreva o primeiro turno abaixo.</p>
          )}
          <div ref={bottomRef} />
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
