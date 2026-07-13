"use client";

import { Pencil, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { toast } from "sonner";
import { mutate } from "swr";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, type Character, type Location, type Relation, type StoryBeat } from "@/lib/api";
import { useMemoryState } from "@/lib/hooks";

import { RelationsGraph } from "./relations-graph";

function Empty({ label }: { label: string }) {
  return <p className="p-2 text-xs text-muted-foreground">Nada em {label} ainda.</p>;
}

function initial(name: string): string {
  return (name.trim()[0] ?? "?").toUpperCase();
}

function avatarStyle(name: string): { backgroundColor: string } {
  const hue = [...name].reduce((acc, ch) => acc + ch.charCodeAt(0), 0) % 360;
  return { backgroundColor: `hsl(${hue} 55% 42%)` };
}

function Avatar({ name }: { name: string }) {
  return (
    <span
      style={avatarStyle(name)}
      className="flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
      aria-hidden
    >
      {initial(name)}
    </span>
  );
}

function DeleteFact({ label, onConfirm }: { label: string; onConfirm: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  async function go() {
    setBusy(true);
    try {
      await onConfirm();
      setOpen(false);
    } catch (err) {
      toast.error(`Falha ao apagar: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className={buttonVariants({ variant: "ghost", size: "sm", className: "size-7 p-0" })}
        aria-label={`apagar ${label}`}
      >
        <Trash2 className="size-3.5" />
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Apagar {label}?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Remove esse fato do world_state — some do inspector e do contexto dos próximos turnos.
        </p>
        <DialogFooter>
          <Button variant="destructive" size="sm" disabled={busy} onClick={go}>
            Apagar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditDialog({
  title,
  children,
  onSave,
}: {
  title: string;
  children: ReactNode;
  onSave: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  async function go() {
    setBusy(true);
    try {
      await onSave();
      setOpen(false);
    } catch (err) {
      toast.error(`Falha ao salvar: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className={buttonVariants({ variant: "ghost", size: "sm", className: "size-7 p-0" })}
        aria-label={`editar ${title}`}
      >
        <Pencil className="size-3.5" />
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Editar {title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">{children}</div>
        <DialogFooter>
          <Button size="sm" disabled={busy} onClick={go}>
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Actions({ children }: { children: ReactNode }) {
  return <div className="ml-auto flex shrink-0 gap-0.5">{children}</div>;
}

export function MemoryInspector({ sessionId }: { sessionId: string }) {
  const { data } = useMemoryState(sessionId);
  const characters = data?.characters ?? [];
  const locations = data?.locations ?? [];
  const relations = data?.relations ?? [];
  const beats = data?.story_beats ?? [];
  const nameById = new Map(characters.map((c) => [c.id, c.name]));
  const refresh = () => mutate(`state:${sessionId}`);

  function relationSummary(characterId: number): string {
    const involved = relations.filter(
      (r) => r.a_character_id === characterId || r.b_character_id === characterId,
    );
    const byKind = involved.reduce<Record<string, number>>((acc, r) => {
      acc[r.kind] = (acc[r.kind] ?? 0) + 1;
      return acc;
    }, {});
    return Object.entries(byKind)
      .map(([kind, n]) => `${n} ${kind}`)
      .join(" · ");
  }

  return (
    <Tabs defaultValue="chars" className="flex flex-col h-full">
      <TabsList className="grid grid-cols-4 m-2">
        <TabsTrigger value="chars">Personagens ({characters.length})</TabsTrigger>
        <TabsTrigger value="locs">Locais ({locations.length})</TabsTrigger>
        <TabsTrigger value="rels">Relações ({relations.length})</TabsTrigger>
        <TabsTrigger value="beats">Beats ({beats.length})</TabsTrigger>
      </TabsList>
      <ScrollArea className="flex-1 min-h-0 px-2 pb-2">
        <TabsContent value="chars" className="space-y-2">
          {characters.map((c) => (
            <Card key={c.id} className="p-3" data-testid="character-card">
              <div className="flex items-start gap-2">
                <Avatar name={c.name} />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{c.name}</div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.traits.map((t) => (
                      <Badge key={t} variant="secondary">
                        {t}
                      </Badge>
                    ))}
                  </div>
                </div>
                <Actions>
                  <CharacterEdit sessionId={sessionId} character={c} onSaved={refresh} />
                  <DeleteFact
                    label={c.name}
                    onConfirm={async () => {
                      await api.deleteCharacter(sessionId, c.id);
                      await refresh();
                    }}
                  />
                </Actions>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                turnos {c.first_appeared_turn}–{c.last_seen_turn}
                {relationSummary(c.id) && ` · ${relationSummary(c.id)}`}
              </div>
            </Card>
          ))}
          {characters.length === 0 && <Empty label="personagens" />}
        </TabsContent>

        <TabsContent value="locs" className="space-y-2">
          {locations.map((l) => (
            <Card key={l.id} className="p-3">
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{l.name}</div>
                  {l.description && (
                    <div className="text-xs text-muted-foreground">{l.description}</div>
                  )}
                  <div className="mt-1 text-xs text-muted-foreground">
                    visitado no turno {l.first_visited_turn}
                  </div>
                </div>
                <Actions>
                  <LocationEdit sessionId={sessionId} location={l} onSaved={refresh} />
                  <DeleteFact
                    label={l.name}
                    onConfirm={async () => {
                      await api.deleteLocation(sessionId, l.id);
                      await refresh();
                    }}
                  />
                </Actions>
              </div>
            </Card>
          ))}
          {locations.length === 0 && <Empty label="locais" />}
        </TabsContent>

        <TabsContent value="rels" className="space-y-2">
          <RelationsGraph characters={characters} relations={relations} />
          {relations.map((r) => (
            <Card key={r.id} className="flex items-start gap-2 p-3 text-sm">
              <div className="min-w-0 flex-1">
                <span className="font-medium">
                  {nameById.get(r.a_character_id) ?? `#${r.a_character_id}`} ↔{" "}
                  {nameById.get(r.b_character_id) ?? `#${r.b_character_id}`}
                </span>
                <div className="text-xs text-muted-foreground">
                  {r.kind} · valência {r.valence > 0 ? `+${r.valence}` : r.valence} · desde o turno{" "}
                  {r.since_turn}
                </div>
              </div>
              <Actions>
                <RelationEdit sessionId={sessionId} relation={r} onSaved={refresh} />
                <DeleteFact
                  label="relação"
                  onConfirm={async () => {
                    await api.deleteRelation(sessionId, r.id);
                    await refresh();
                  }}
                />
              </Actions>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="beats" className="space-y-2">
          {beats.map((b) => (
            <Card key={b.id} className="flex items-start gap-2 p-3">
              <div className="min-w-0 flex-1">
                <div className="text-xs font-medium text-muted-foreground">turno {b.turn}</div>
                <div className="text-sm">{b.summary}</div>
              </div>
              <Actions>
                <BeatEdit sessionId={sessionId} beat={b} onSaved={refresh} />
                <DeleteFact
                  label="beat"
                  onConfirm={async () => {
                    await api.deleteStoryBeat(sessionId, b.id);
                    await refresh();
                  }}
                />
              </Actions>
            </Card>
          ))}
          {beats.length === 0 && <Empty label="story beats" />}
        </TabsContent>
      </ScrollArea>
    </Tabs>
  );
}

function CharacterEdit({
  sessionId,
  character,
  onSaved,
}: {
  sessionId: string;
  character: Character;
  onSaved: () => void;
}) {
  const [name, setName] = useState(character.name);
  const [traits, setTraits] = useState(character.traits.join(", "));
  return (
    <EditDialog
      title="personagem"
      onSave={async () => {
        await api.updateCharacter(sessionId, character.id, {
          name,
          traits: traits
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean),
          first_appeared_turn: character.first_appeared_turn,
          last_seen_turn: character.last_seen_turn,
        });
        onSaved();
      }}
    >
      <Input aria-label="nome" value={name} onChange={(e) => setName(e.target.value)} />
      <Input
        aria-label="traços (separados por vírgula)"
        placeholder="traços separados por vírgula"
        value={traits}
        onChange={(e) => setTraits(e.target.value)}
      />
    </EditDialog>
  );
}

function LocationEdit({
  sessionId,
  location,
  onSaved,
}: {
  sessionId: string;
  location: Location;
  onSaved: () => void;
}) {
  const [name, setName] = useState(location.name);
  const [description, setDescription] = useState(location.description);
  return (
    <EditDialog
      title="local"
      onSave={async () => {
        await api.updateLocation(sessionId, location.id, {
          name,
          description,
          first_visited_turn: location.first_visited_turn,
        });
        onSaved();
      }}
    >
      <Input aria-label="nome" value={name} onChange={(e) => setName(e.target.value)} />
      <Textarea
        aria-label="descrição"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
    </EditDialog>
  );
}

function RelationEdit({
  sessionId,
  relation,
  onSaved,
}: {
  sessionId: string;
  relation: Relation;
  onSaved: () => void;
}) {
  const [kind, setKind] = useState(relation.kind);
  const [valence, setValence] = useState(String(relation.valence));
  return (
    <EditDialog
      title="relação"
      onSave={async () => {
        await api.updateRelation(sessionId, relation.id, {
          a_character_id: relation.a_character_id,
          b_character_id: relation.b_character_id,
          kind,
          valence: Number.parseInt(valence, 10) || 0,
          since_turn: relation.since_turn,
        });
        onSaved();
      }}
    >
      <Input aria-label="tipo" value={kind} onChange={(e) => setKind(e.target.value)} />
      <Input
        aria-label="valência"
        type="number"
        value={valence}
        onChange={(e) => setValence(e.target.value)}
      />
    </EditDialog>
  );
}

function BeatEdit({
  sessionId,
  beat,
  onSaved,
}: {
  sessionId: string;
  beat: StoryBeat;
  onSaved: () => void;
}) {
  const [summary, setSummary] = useState(beat.summary);
  return (
    <EditDialog
      title="beat"
      onSave={async () => {
        await api.updateStoryBeat(sessionId, beat.id, {
          summary,
          turn: beat.turn,
          importance: beat.importance,
          tags: beat.tags,
        });
        onSaved();
      }}
    >
      <Textarea aria-label="resumo" value={summary} onChange={(e) => setSummary(e.target.value)} />
    </EditDialog>
  );
}
