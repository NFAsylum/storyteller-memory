"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useMemoryState } from "@/lib/hooks";

function Empty({ label }: { label: string }) {
  return <p className="p-2 text-xs text-muted-foreground">Nada em {label} ainda.</p>;
}

export function MemoryInspector({ sessionId }: { sessionId: string }) {
  const { data } = useMemoryState(sessionId);
  const characters = data?.characters ?? [];
  const locations = data?.locations ?? [];
  const relations = data?.relations ?? [];
  const beats = data?.story_beats ?? [];
  const nameById = new Map(characters.map((c) => [c.id, c.name]));

  return (
    <Tabs defaultValue="chars" className="flex flex-col h-full">
      <TabsList className="grid grid-cols-4 m-2">
        <TabsTrigger value="chars">Personagens ({characters.length})</TabsTrigger>
        <TabsTrigger value="locs">Locais ({locations.length})</TabsTrigger>
        <TabsTrigger value="rels">Relações ({relations.length})</TabsTrigger>
        <TabsTrigger value="beats">Beats ({beats.length})</TabsTrigger>
      </TabsList>
      <ScrollArea className="flex-1 px-2 pb-2">
        <TabsContent value="chars" className="space-y-2">
          {characters.map((c) => (
            <Card key={c.id} className="p-3" data-testid="character-card">
              <div className="text-sm font-medium">{c.name}</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {c.traits.map((t) => (
                  <Badge key={t} variant="secondary">
                    {t}
                  </Badge>
                ))}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                apareceu no turno {c.first_appeared_turn}
              </div>
            </Card>
          ))}
          {characters.length === 0 && <Empty label="personagens" />}
        </TabsContent>

        <TabsContent value="locs" className="space-y-2">
          {locations.map((l) => (
            <Card key={l.name} className="p-3">
              <div className="text-sm font-medium">{l.name}</div>
              {l.description && <div className="text-xs text-muted-foreground">{l.description}</div>}
              <div className="mt-1 text-xs text-muted-foreground">
                visitado no turno {l.first_visited_turn}
              </div>
            </Card>
          ))}
          {locations.length === 0 && <Empty label="locais" />}
        </TabsContent>

        <TabsContent value="rels" className="space-y-2">
          {relations.map((r, i) => (
            <Card key={i} className="p-3 text-sm">
              <span className="font-medium">
                {nameById.get(r.a_character_id) ?? `#${r.a_character_id}`} ↔{" "}
                {nameById.get(r.b_character_id) ?? `#${r.b_character_id}`}
              </span>
              <div className="text-xs text-muted-foreground">
                {r.kind} · valência {r.valence > 0 ? `+${r.valence}` : r.valence} · desde o turno{" "}
                {r.since_turn}
              </div>
            </Card>
          ))}
          {relations.length === 0 && <Empty label="relações" />}
        </TabsContent>

        <TabsContent value="beats" className="space-y-0">
          <ol className="relative ml-3 border-l pl-4">
            {beats.map((b, i) => (
              <li key={i} className="mb-3">
                <div className="text-xs font-medium text-muted-foreground">turno {b.turn}</div>
                <div className="text-sm">{b.summary}</div>
              </li>
            ))}
          </ol>
          {beats.length === 0 && <Empty label="story beats" />}
        </TabsContent>
      </ScrollArea>
    </Tabs>
  );
}
