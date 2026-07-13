"use client";

import { Settings2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { mutate } from "swr";

import { OptionGroup } from "@/components/option-group";
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
import { api, DEFAULT_CONFIG, type SessionConfig } from "@/lib/api";
import {
  configSummary,
  GENRES,
  INTENSITIES,
  LENGTHS,
  POVS,
  ROLES,
  TONES,
} from "@/lib/config-options";
import { useSession } from "@/lib/hooks";

export function SessionConfigChip({ sessionId }: { sessionId: string }) {
  const { data: session } = useSession(sessionId);
  const config = session?.config ?? DEFAULT_CONFIG;
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<SessionConfig>(config);
  const [busy, setBusy] = useState(false);

  function set<K extends keyof SessionConfig>(key: K, value: SessionConfig[K]) {
    setDraft((c) => ({ ...c, [key]: value }));
  }

  async function save() {
    setBusy(true);
    try {
      await api.patchConfig(sessionId, draft);
      await mutate(`session:${sessionId}`);
      setOpen(false);
    } catch (err) {
      toast.error(`Falha ao salvar: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) setDraft(config);
      }}
    >
      <DialogTrigger
        className={buttonVariants({ variant: "outline", size: "sm", className: "h-7 gap-1 text-xs" })}
        aria-label="editar controles da história"
      >
        <Settings2 className="size-3.5" /> {configSummary(config)}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Controles da história</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <OptionGroup label="Gênero" value={draft.genre} options={GENRES} onChange={(v) => set("genre", v)} />
          <OptionGroup label="Tom" value={draft.tone} options={TONES} onChange={(v) => set("tone", v)} />
          <OptionGroup label="Ponto de vista" value={draft.pov} options={POVS} onChange={(v) => set("pov", v)} />
          <OptionGroup label="Extensão" value={draft.target_length} options={LENGTHS} onChange={(v) => set("target_length", v)} />
          <OptionGroup label="Intensidade" value={draft.content_intensity} options={INTENSITIES} onChange={(v) => set("content_intensity", v)} />
          <OptionGroup
            label="Você é…"
            value={draft.protagonist.role}
            options={ROLES}
            onChange={(v) => set("protagonist", { ...draft.protagonist, role: v })}
          />
          {draft.protagonist.role === "protagonist" && (
            <div className="space-y-2">
              <Input
                placeholder="Nome do personagem"
                aria-label="nome do personagem"
                value={draft.protagonist.character_name}
                onChange={(e) => set("protagonist", { ...draft.protagonist, character_name: e.target.value })}
              />
              <Input
                placeholder="Papel (opcional)"
                aria-label="papel do personagem"
                value={draft.protagonist.character_role}
                onChange={(e) => set("protagonist", { ...draft.protagonist, character_role: e.target.value })}
              />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button onClick={save} disabled={busy}>
            {busy ? "Salvando…" : "Salvar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
