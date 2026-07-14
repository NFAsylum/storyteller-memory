"use client";

import { useHealth } from "@/lib/hooks";

// Small transparency chip in the workspace header: which LLM backend + model is
// actually serving. The model is queried live from llama-server (env config is only a
// hint about what was requested, not what's loaded), so this reflects reality. Display
// only — no switching UX (Option A of the backend/model comparativo).
const BACKEND_STYLES: Record<string, string> = {
  local: "border-amber-500/40 text-amber-600 dark:text-amber-400",
  anthropic: "border-green-500/40 text-green-600 dark:text-green-400",
  fake: "border-muted-foreground/30 text-muted-foreground",
};

const BASE =
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap";

export function ModelStatusChip() {
  const { data, error, isLoading } = useHealth();

  if (isLoading) {
    return (
      <span className={`${BASE} border-muted-foreground/30 text-muted-foreground`}>
        carregando…
      </span>
    );
  }

  if (error || !data) {
    return (
      <span
        className={`${BASE} border-destructive/40 text-destructive`}
        title="Não foi possível consultar o backend"
      >
        backend offline
      </span>
    );
  }

  const style = BACKEND_STYLES[data.backend_llm] ?? BACKEND_STYLES.fake;
  const tooltip = `Backend LLM: ${data.backend_llm} · Model: ${data.llm_model} · Para trocar: edite .env e reinicie`;

  return (
    <span className={`${BASE} ${style}`} title={tooltip} data-testid="model-status-chip">
      <span className="opacity-70">{data.backend_llm}</span>
      <span aria-hidden>·</span>
      <span>{data.llm_model}</span>
    </span>
  );
}
