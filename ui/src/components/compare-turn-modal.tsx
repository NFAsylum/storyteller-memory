"use client";

import { GitCompare } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type CompareResult } from "@/lib/api";

export function CompareTurnModal({ sessionId }: { sessionId: string }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CompareResult | null>(null);

  async function run() {
    setOpen(true);
    setBusy(true);
    setResult(null);
    try {
      setResult(await api.compareTurn(sessionId));
    } catch (err) {
      toast.error(`Falha ao comparar: ${(err as Error).message}`);
      setOpen(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className={buttonVariants({ variant: "secondary", size: "sm", className: "w-full justify-start" })}
        onClick={run}
      >
        <GitCompare className="size-4" /> Comparar com/sem memória
      </DialogTrigger>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Mesmo turno, com e sem memória</DialogTitle>
        </DialogHeader>
        {result && (
          <p className="text-xs text-muted-foreground">
            Turno reexecutado: <span className="italic">{result.user_input}</span>
          </p>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-md border p-3" data-testid="compare-no-memory">
            <div className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              Sem memória
            </div>
            {busy ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <p className="text-sm whitespace-pre-wrap">{result?.no_memory.narrator}</p>
            )}
          </div>
          <div className="rounded-md border border-primary/40 bg-primary/5 p-3" data-testid="compare-mem0">
            <div className="mb-2 text-xs font-semibold uppercase text-primary">Com memória</div>
            {busy ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <p className="text-sm whitespace-pre-wrap">{result?.mem0_only.narrator}</p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
