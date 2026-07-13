"use client";

import { buttonVariants, Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

import { SetupWizard } from "./setup-wizard";
import { ThemeToggle } from "./theme-toggle";

function HowItWorks() {
  return (
    <Dialog>
      <DialogTrigger className={buttonVariants({ variant: "outline" })}>Como funciona</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Como a memória funciona</DialogTitle>
        </DialogHeader>
        <ol className="space-y-2 text-sm">
          <li>1. Cada turno que você escreve é indexado num vetor (mem0).</li>
          <li>2. A cada 2 turnos, o LLM consolida os fatos: personagens, locais, relações, beats.</li>
          <li>
            3. No próximo turno, o contexto relevante é recuperado e injetado — a história
            &ldquo;lembra&rdquo; do que já aconteceu.
          </li>
        </ol>
      </DialogContent>
    </Dialog>
  );
}

export function Hero({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="relative flex min-h-screen flex-1 flex-col items-center justify-center gap-6 p-6 text-center">
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <div className="max-w-xl space-y-3">
        <h1 className="text-3xl font-semibold">Storyteller</h1>
        <p className="text-muted-foreground">
          Um contador de histórias com <strong>memória de longo prazo verificável</strong>:
          personagens, lugares e relações são catalogados automaticamente e voltam nos próximos
          turnos.
        </p>
        <p className="rounded-md border border-primary/30 bg-primary/5 p-2 text-sm">
          O diferencial: o botão <strong>&ldquo;Comparar com/sem memória&rdquo;</strong> mostra a
          mesma cena com e sem o sistema de memória — é o ponto do produto.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <SetupWizard />
        <HowItWorks />
        <Button variant="ghost" onClick={onDismiss}>
          Explorar sessões
        </Button>
      </div>
    </div>
  );
}
