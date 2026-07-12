"use client";

import { useEffect } from "react";

import { Workspace } from "@/components/workspace";
import { saveSessionCookie } from "@/lib/session-cookie";

export function SessionClient({ id }: { id: string }) {
  useEffect(() => saveSessionCookie(id), [id]);
  return <Workspace activeId={id} />;
}
