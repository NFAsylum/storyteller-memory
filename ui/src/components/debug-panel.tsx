"use client";

import { Brain, Eye, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { mutate } from "swr";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { api, type ContextBundle } from "@/lib/api";
import { useSession } from "@/lib/hooks";
import { clearSessionCookie } from "@/lib/session-cookie";

import { CompareTurnModal } from "./compare-turn-modal";

export function DebugPanel({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const { data: session } = useSession(sessionId);
  const [bundle, setBundle] = useState<ContextBundle | null>(null);

  async function reflect() {
    try {
      const r = await api.reflect(sessionId);
      await Promise.all([mutate(`state:${sessionId}`), mutate(`session:${sessionId}`)]);
      if (r.failed) toast.warning("Reflection falhou ao gerar JSON válido.");
      else
        toast.success(
          `Reflection: ${r.characters_updated} personagens, ${r.beats_created} beats.`,
        );
    } catch (err) {
      toast.error(`Falha na reflection: ${(err as Error).message}`);
    }
  }

  async function showRetrieved() {
    if (!session || session.last_turn === 0) {
      toast.info("Nenhum turno ainda.");
      return;
    }
    try {
      setBundle(await api.turnContext(sessionId, session.last_turn));
    } catch (err) {
      toast.error(`Falha ao buscar contexto: ${(err as Error).message}`);
    }
  }

  async function clearSession() {
    try {
      await api.deleteSession(sessionId);
      clearSessionCookie();
      await mutate("sessions");
      router.push("/");
    } catch (err) {
      toast.error(`Falha ao limpar: ${(err as Error).message}`);
    }
  }

  return (
    <div className="border-t p-2 space-y-2">
      <CompareTurnModal sessionId={sessionId} />

      <Button variant="secondary" size="sm" className="w-full justify-start" onClick={reflect}>
        <Brain className="size-4" /> Forçar reflection
      </Button>

      <Dialog>
        <DialogTrigger
          className={buttonVariants({ variant: "secondary", size: "sm", className: "w-full justify-start" })}
          onClick={showRetrieved}
        >
          <Eye className="size-4" /> Contexto do último turno
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Contexto recuperado (último turno)</DialogTitle>
          </DialogHeader>
          {bundle ? (
            <div className="space-y-2 text-sm">
              <div>
                <span className="font-medium">Personagens ativos:</span>{" "}
                {bundle.active_characters.join(", ") || "—"}
              </div>
              <div>
                <span className="font-medium">Fatos:</span>{" "}
                {bundle.structured_facts.join("; ") || "—"}
              </div>
              <div>
                <span className="font-medium">Memórias ({bundle.raw_memories.length}):</span>
                <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted p-2 text-xs whitespace-pre-wrap">
                  {bundle.raw_memories.join("\n") || "—"}
                </pre>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Sem contexto.</p>
          )}
        </DialogContent>
      </Dialog>

      <Separator />

      <Dialog>
        <DialogTrigger
          className={buttonVariants({ variant: "destructive", size: "sm", className: "w-full justify-start" })}
        >
          <Trash2 className="size-4" /> Limpar sessão
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Apagar esta sessão?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Isso apaga a sessão, os turnos, as memórias (mem0) e o world_state. Não dá pra desfazer.
          </p>
          <DialogFooter>
            <Button variant="destructive" onClick={clearSession}>
              Apagar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
