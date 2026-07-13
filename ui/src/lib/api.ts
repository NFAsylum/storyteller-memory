// Typed client for the Storyteller FastAPI backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Genre =
  | "fantasy"
  | "scifi"
  | "horror"
  | "mystery"
  | "romance"
  | "literary"
  | "comedy";
export type Pov = "first_person" | "third_limited" | "third_omniscient";
export type Tone = "serious" | "comedic" | "gothic" | "cyberpunk" | "cozy" | "dark";
export type ContentIntensity = "sfw" | "mature" | "dark";
export type TargetLength = "brief" | "medium" | "long";
export type ProtagonistRole = "protagonist" | "author" | "narrator";

export interface Protagonist {
  role: ProtagonistRole;
  character_name: string;
  character_role: string;
}

export interface SessionConfig {
  genre: Genre;
  pov: Pov;
  tone: Tone;
  content_intensity: ContentIntensity;
  target_length: TargetLength;
  protagonist: Protagonist;
}

export const DEFAULT_CONFIG: SessionConfig = {
  genre: "fantasy",
  pov: "third_limited",
  tone: "serious",
  content_intensity: "sfw",
  target_length: "medium",
  protagonist: { role: "author", character_name: "", character_role: "" },
};

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
  id: number;
  name: string;
  description: string;
  first_visited_turn: number;
}

export interface Relation {
  id: number;
  a_character_id: number;
  b_character_id: number;
  kind: string;
  valence: number;
  since_turn: number;
}

export interface StoryBeat {
  id: number;
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
  config: SessionConfig;
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
  createSession: (name: string, brief = "", config?: SessionConfig) =>
    request<{ id: string; name: string; last_turn: number; config: SessionConfig }>("/sessions", {
      method: "POST",
      body: JSON.stringify({ name, brief, ...(config ? { config } : {}) }),
    }),
  getSession: (id: string) => request<SessionDetail>(`/sessions/${id}`),
  patchConfig: (id: string, config: SessionConfig) =>
    request<{ id: string; config: SessionConfig }>(`/sessions/${id}/config`, {
      method: "PATCH",
      body: JSON.stringify(config),
    }),
  storyStarters: (genre: Genre) =>
    request<{ genre: string; starters: string[] }>(`/story-starters?genre=${genre}`),
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

  updateCharacter: (id: string, characterId: number, body: Omit<Character, "id">) =>
    request<Character>(`/sessions/${id}/state/characters/${characterId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteCharacter: (id: string, characterId: number) =>
    request<void>(`/sessions/${id}/state/characters/${characterId}`, { method: "DELETE" }),

  updateLocation: (id: string, locationId: number, body: Omit<Location, "id">) =>
    request<Location>(`/sessions/${id}/state/locations/${locationId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteLocation: (id: string, locationId: number) =>
    request<void>(`/sessions/${id}/state/locations/${locationId}`, { method: "DELETE" }),

  updateRelation: (id: string, relationId: number, body: Omit<Relation, "id">) =>
    request<Relation>(`/sessions/${id}/state/relations/${relationId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteRelation: (id: string, relationId: number) =>
    request<void>(`/sessions/${id}/state/relations/${relationId}`, { method: "DELETE" }),

  updateStoryBeat: (id: string, beatId: number, body: Omit<StoryBeat, "id">) =>
    request<StoryBeat>(`/sessions/${id}/state/story-beats/${beatId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteStoryBeat: (id: string, beatId: number) =>
    request<void>(`/sessions/${id}/state/story-beats/${beatId}`, { method: "DELETE" }),

  editTurn: (id: string, turnNumber: number, text: string) =>
    request<{ turn_number: number; user_input: string; narrator_text: string }>(
      `/sessions/${id}/turns/${turnNumber}`,
      { method: "PATCH", body: JSON.stringify({ text }) },
    ),
  regenerateTurn: (id: string, turnNumber: number) =>
    request<{ turn_number: number; narrator_text: string }>(
      `/sessions/${id}/turns/${turnNumber}/regenerate`,
      { method: "POST" },
    ),
  deleteTurn: (id: string, turnNumber: number) =>
    request<void>(`/sessions/${id}/turns/${turnNumber}`, { method: "DELETE" }),
  forkSession: (id: string, fromTurn: number) =>
    request<{ id: string; name: string; last_turn: number }>(
      `/sessions/${id}/fork?from_turn=${fromTurn}`,
      { method: "POST" },
    ),
  exportUrl: (id: string, format: "markdown" | "txt" | "json") =>
    `${API_URL}/sessions/${id}/export?format=${format}`,
};
