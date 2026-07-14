"use client";

import useSWR from "swr";

import {
  api,
  type HealthStatus,
  type MemoryState,
  type SessionDetail,
  type SessionSummary,
} from "./api";

export function useSessions() {
  return useSWR<SessionSummary[]>("sessions", api.listSessions);
}

// Backend + live model status, polled every 30s (matches the server-side detect cache).
export function useHealth() {
  return useSWR<HealthStatus>("health", api.health, {
    refreshInterval: 30_000,
    revalidateOnFocus: false,
  });
}

export function useSession(id: string | null) {
  return useSWR<SessionDetail>(id ? `session:${id}` : null, () => api.getSession(id as string));
}

export function useMemoryState(id: string | null) {
  return useSWR<MemoryState>(id ? `state:${id}` : null, () => api.getState(id as string));
}
