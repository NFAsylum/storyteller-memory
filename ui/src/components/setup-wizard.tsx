"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
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
import { GENRES, INTENSITIES, LENGTHS, POVS, ROLES, TONES } from "@/lib/config-options";
import { saveSessionCookie } from "@/lib/session-cookie";

const STEP_TITLES = ["Story & tone", "Voice", "Who are you?", "Start with…"];

export function SetupWizard() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [config, setConfig] = useState<SessionConfig>(DEFAULT_CONFIG);
  const [starter, setStarter] = useState("");
  const [starters, setStarters] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  function set<K extends keyof SessionConfig>(key: K, value: SessionConfig[K]) {
    setConfig((c) => ({ ...c, [key]: value }));
  }

  async function loadStarters() {
    try {
      setStarters((await api.storyStarters(config.genre)).starters);
    } catch {
      setStarters([]);
    }
  }

  async function next() {
    if (step === 2) await loadStarters();
    setStep((s) => Math.min(3, s + 1));
  }

  async function create() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const session = await api.createSession(name.trim(), "", config);
      saveSessionCookie(session.id);
      await mutate("sessions");
      setOpen(false);
      const query = starter ? `?starter=${encodeURIComponent(starter)}` : "";
      router.push(`/sessions/${session.id}${query}`);
    } catch (err) {
      toast.error(`Falha ao criar sessão: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) {
          setStep(0);
          setName("");
          setConfig(DEFAULT_CONFIG);
          setStarter("");
        }
      }}
    >
      <DialogTrigger className={buttonVariants({ variant: "outline", size: "sm" })}>
        <Plus className="size-4" /> Nova
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Nova história — {STEP_TITLES[step]} ({step + 1}/4)
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-1">
          {step === 0 && (
            <>
              <Input
                placeholder="Nome da história"
                aria-label="nome da história"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <OptionGroup label="Gênero" value={config.genre} options={GENRES} onChange={(v) => set("genre", v)} />
              <OptionGroup label="Tom" value={config.tone} options={TONES} onChange={(v) => set("tone", v)} />
            </>
          )}
          {step === 1 && (
            <>
              <OptionGroup label="Ponto de vista" value={config.pov} options={POVS} onChange={(v) => set("pov", v)} />
              <OptionGroup label="Extensão do turno" value={config.target_length} options={LENGTHS} onChange={(v) => set("target_length", v)} />
              <OptionGroup label="Intensidade" value={config.content_intensity} options={INTENSITIES} onChange={(v) => set("content_intensity", v)} />
            </>
          )}
          {step === 2 && (
            <>
              <OptionGroup
                label="Você é…"
                value={config.protagonist.role}
                options={ROLES}
                onChange={(v) => set("protagonist", { ...config.protagonist, role: v })}
              />
              {config.protagonist.role === "protagonist" && (
                <div className="space-y-2">
                  <Input
                    placeholder="Nome do personagem"
                    aria-label="nome do personagem"
                    value={config.protagonist.character_name}
                    onChange={(e) => set("protagonist", { ...config.protagonist, character_name: e.target.value })}
                  />
                  <Input
                    placeholder="Papel (ex.: cavaleiro, detetive) — opcional"
                    aria-label="papel do personagem"
                    value={config.protagonist.character_role}
                    onChange={(e) => set("protagonist", { ...config.protagonist, character_role: e.target.value })}
                  />
                </div>
              )}
            </>
          )}
          {step === 3 && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Escolha uma abertura (edita depois) ou comece do zero.
              </p>
              <div className="space-y-1.5" role="group" aria-label="story starters">
                {starters.map((s) => (
                  <button
                    key={s}
                    type="button"
                    aria-pressed={starter === s}
                    onClick={() => setStarter(s)}
                    className={`w-full rounded-md border p-2 text-left text-sm hover:bg-accent ${
                      starter === s ? "border-primary bg-primary/5" : ""
                    }`}
                  >
                    {s}
                  </button>
                ))}
                <button
                  type="button"
                  aria-pressed={starter === ""}
                  onClick={() => setStarter("")}
                  className={`w-full rounded-md border p-2 text-left text-sm hover:bg-accent ${
                    starter === "" ? "border-primary bg-primary/5" : ""
                  }`}
                >
                  Começar do zero
                </button>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="sm:justify-between">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={step === 0}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
          >
            Voltar
          </Button>
          {step < 3 ? (
            <Button type="button" size="sm" disabled={step === 0 && !name.trim()} onClick={next}>
              Próximo
            </Button>
          ) : (
            <Button type="button" size="sm" disabled={busy || !name.trim()} onClick={create}>
              {busy ? "Criando…" : "Criar história"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
