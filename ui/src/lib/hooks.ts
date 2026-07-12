"use client";

import useSWR from "swr";

import { api, type MemoryState, type SessionDetail, type SessionSummary } from "./api";

export function useSessions() {
  return useSWR<SessionSummary[]>("sessions", api.listSessions);
}

export function useSession(id: string | null) {
  return useSWR<SessionDetail>(id ? `session:${id}` : null, () => api.getSession(id as string));
}

export function useMemoryState(id: string | null) {
  return useSWR<MemoryState>(id ? `state:${id}` : null, () => api.getState(id as string));
}
