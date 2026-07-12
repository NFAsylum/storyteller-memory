"use client";

import { Plus } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { saveSessionCookie } from "@/lib/session-cookie";

export function NewSessionDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);

  async function create() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const session = await api.createSession(name.trim(), brief.trim());
      saveSessionCookie(session.id);
      await mutate("sessions");
      setOpen(false);
      setName("");
      setBrief("");
      router.push(`/sessions/${session.id}`);
    } catch (err) {
      toast.error(`Falha ao criar sessão: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger className={buttonVariants({ variant: "outline", size: "sm" })}>
        <Plus className="size-4" /> Nova
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nova sessão</DialogTitle>
        </DialogHeader>
        <Input
          placeholder="Nome da história"
          aria-label="nome da sessão"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Textarea
          placeholder="Brief inicial (opcional)"
          aria-label="brief inicial"
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
        />
        <DialogFooter>
          <Button onClick={create} disabled={busy || !name.trim()}>
            {busy ? "Criando…" : "Criar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
