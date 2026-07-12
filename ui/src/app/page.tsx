"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Workspace } from "@/components/workspace";
import { api } from "@/lib/api";
import { readSessionCookie } from "@/lib/session-cookie";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Resume the last session if the cookie points at one that still exists.
    const id = readSessionCookie();
    if (!id) return;
    api
      .getSession(id)
      .then(() => router.replace(`/sessions/${id}`))
      .catch(() => {});
  }, [router]);

  return <Workspace activeId={null} />;
}
