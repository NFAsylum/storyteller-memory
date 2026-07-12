// Typed client for the Storyteller FastAPI backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SessionSummary {
  id: string;
  name: string;
  last_turn: number;
  created_at: string;
}

export interface Turn {
  turn_number: number;
  user_input: string;
  narrator_text: string;
  created_at: string;
}

export interface Character {
  id: number;
  name: string;
  traits: string[];
  first_appeared_turn: number;
  last_seen_turn: number;
}

export interface Location {
  name: string;
  description: string;
  first_visited_turn: number;
}

export interface Relation {
  a_character_id: number;
  b_character_id: number;
  kind: string;
  valence: number;
  since_turn: number;
}

export interface StoryBeat {
  summary: string;
  turn: number;
  importance: number;
  tags: string[];
}

export interface MemoryState {
  characters: Character[];
  locations: Location[];
  relations: Relation[];
  story_beats: StoryBeat[];
}

export interface SessionDetail {
  id: string;
  name: string;
  brief: string;
  last_turn: number;
  turns: Turn[];
  memory_state: MemoryState;
}

export interface ContextBundle {
  raw_memories: string[];
  structured_facts: string[];
  active_characters: string[];
  token_estimate: number;
  turn: number;
}

export interface TurnResult {
  turn_number: number;
  narrator_text: string;
  retrieved_context: ContextBundle;
  cost_usd: number;
}

export interface ReflectResult {
  beats_created: number;
  characters_updated: number;
  relations_updated: number;
  cost_usd: number;
  failed: boolean;
}

export interface CompareResult {
  user_input: string;
  no_memory: { narrator: string; retrieved: null };
  mem0_only: { narrator: string; retrieved: ContextBundle };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  listSessions: () => request<SessionSummary[]>("/sessions"),
  createSession: (name: string, brief = "") =>
    request<{ id: string; name: string; last_turn: number }>("/sessions", {
      method: "POST",
      body: JSON.stringify({ name, brief }),
    }),
  getSession: (id: string) => request<SessionDetail>(`/sessions/${id}`),
  deleteSession: (id: string) => request<void>(`/sessions/${id}`, { method: "DELETE" }),
  runTurn: (id: string, text: string) =>
    request<TurnResult>(`/sessions/${id}/turn`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  turnContext: (id: string, turnNumber: number) =>
    request<ContextBundle>(`/sessions/${id}/turns/${turnNumber}/context`),
  reflect: (id: string) => request<ReflectResult>(`/sessions/${id}/reflect`, { method: "POST" }),
  compareTurn: (id: string) =>
    request<CompareResult>(`/sessions/${id}/compare-turn`, { method: "POST" }),
  getState: (id: string) => request<MemoryState>(`/sessions/${id}/state`),
};
