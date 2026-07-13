"use client";

import { useState } from "react";

import type { Character, Relation } from "@/lib/api";
import { scrollChatToTurn } from "@/lib/scroll-to-turn";

const KIND_COLORS: Record<string, string> = {
  ally: "#16a34a",
  enemy: "#dc2626",
  romantic: "#db2777",
  family: "#2563eb",
  "co-ocorrencia": "#64748b",
};

function kindColor(kind: string): string {
  return KIND_COLORS[kind] ?? "#64748b";
}

function initial(name: string): string {
  return (name.trim()[0] ?? "?").toUpperCase();
}

function nodeColor(name: string): string {
  const hue = [...name].reduce((acc, ch) => acc + ch.charCodeAt(0), 0) % 360;
  return `hsl(${hue} 55% 42%)`;
}

const SIZE = 320;
const CENTER = SIZE / 2;
const BASE_RADIUS = 118;
const NODE_R = 13;

export function RelationsGraph({
  characters,
  relations,
}: {
  characters: Character[];
  relations: Relation[];
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const [hiddenKinds, setHiddenKinds] = useState<Set<string>>(new Set());

  if (relations.length === 0) {
    return (
      <p className="p-3 text-xs text-muted-foreground">
        Nenhuma relação identificada ainda. Relações são detectadas pela reflection ao longo dos
        turnos — escreva mais e observe como o modelo conecta os personagens.
      </p>
    );
  }

  // Order by recency so the most-recently-seen characters take the "notable" top slots.
  const ordered = [...characters].sort((a, b) => b.last_seen_turn - a.last_seen_turn);
  const relCount = new Map<number, number>();
  for (const r of relations) {
    relCount.set(r.a_character_id, (relCount.get(r.a_character_id) ?? 0) + 1);
    relCount.set(r.b_character_id, (relCount.get(r.b_character_id) ?? 0) + 1);
  }

  const pos = new Map<number, { x: number; y: number; deg: number }>();
  ordered.forEach((c, i) => {
    const angle = (i / ordered.length) * 2 * Math.PI - Math.PI / 2;
    const radius = BASE_RADIUS + ((relCount.get(c.id) ?? 0) > 5 ? 14 : 0);
    pos.set(c.id, {
      x: CENTER + radius * Math.cos(angle),
      y: CENTER + radius * Math.sin(angle),
      deg: (angle * 180) / Math.PI,
    });
  });

  const kinds = [...new Set(relations.map((r) => r.kind))];
  const visibleRelations = relations.filter((r) => !hiddenKinds.has(r.kind));

  function toggleKind(kind: string) {
    setHiddenKinds((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  }

  return (
    <div className="space-y-2">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="w-full"
        role="img"
        aria-label="grafo de relações entre personagens"
        data-testid="relations-graph"
      >
        {visibleRelations.map((r) => {
          const a = pos.get(r.a_character_id);
          const b = pos.get(r.b_character_id);
          if (!a || !b) return null;
          const active = hovered === null || hovered === r.a_character_id || hovered === r.b_character_id;
          return (
            <line
              key={r.id}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={kindColor(r.kind)}
              strokeWidth={1 + Math.min(5, Math.abs(r.valence))}
              opacity={active ? 0.7 : 0.12}
            />
          );
        })}
        {ordered.map((c) => {
          const p = pos.get(c.id);
          if (!p) return null;
          const dim = hovered !== null && hovered !== c.id;
          const flip = Math.cos((p.deg * Math.PI) / 180) < 0;
          return (
            <g
              key={c.id}
              data-testid="graph-node"
              className="cursor-pointer"
              opacity={dim ? 0.35 : 1}
              onMouseEnter={() => setHovered(c.id)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => scrollChatToTurn(c.first_appeared_turn)}
            >
              <circle cx={p.x} cy={p.y} r={NODE_R} fill={nodeColor(c.name)} />
              <text
                x={p.x}
                y={p.y}
                dy="0.35em"
                textAnchor="middle"
                fontSize="11"
                fontWeight="600"
                fill="white"
              >
                {initial(c.name)}
              </text>
              <text
                x={p.x + (flip ? -1 : 1) * (NODE_R + 3)}
                y={p.y}
                dy="0.32em"
                textAnchor={flip ? "end" : "start"}
                fontSize="9"
                className="fill-foreground"
                transform={`rotate(${flip ? p.deg + 180 : p.deg} ${
                  p.x + (flip ? -1 : 1) * (NODE_R + 3)
                } ${p.y})`}
              >
                {c.name}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-1 text-[10px] text-muted-foreground">
        <span>espessura = |valência| ·</span>
        {kinds.map((kind) => (
          <button
            key={kind}
            type="button"
            aria-pressed={!hiddenKinds.has(kind)}
            onClick={() => toggleKind(kind)}
            className={`flex items-center gap-1 rounded px-1 hover:bg-accent ${
              hiddenKinds.has(kind) ? "opacity-40 line-through" : ""
            }`}
          >
            <span className="inline-block size-2 rounded-full" style={{ backgroundColor: kindColor(kind) }} />
            {kind}
          </button>
        ))}
      </div>
    </div>
  );
}
