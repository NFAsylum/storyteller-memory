"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Hero } from "@/components/hero";
import { Workspace } from "@/components/workspace";
import { api } from "@/lib/api";
import { readSessionCookie } from "@/lib/session-cookie";

const SEEN_KEY = "storyteller:seen";

export default function Home() {
  const router = useRouter();
  const [view, setView] = useState<"loading" | "hero" | "workspace">("loading");

  useEffect(() => {
    // Resume the last session if the cookie points at one that still exists.
    const id = readSessionCookie();
    if (id) {
      api
        .getSession(id)
        .then(() => router.replace(`/sessions/${id}`))
        .catch(() => setView("workspace"));
      return;
    }
    let seen = false;
    try {
      seen = !!localStorage.getItem(SEEN_KEY);
    } catch {
      // ignore
    }
    setView(seen ? "workspace" : "hero");
  }, [router]);

  if (view === "loading") return null;
  if (view === "hero") {
    return (
      <Hero
        onDismiss={() => {
          try {
            localStorage.setItem(SEEN_KEY, "1");
          } catch {
            // ignore
          }
          setView("workspace");
        }}
      />
    );
  }
  return <Workspace activeId={null} />;
}
