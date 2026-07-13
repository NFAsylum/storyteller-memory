"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { Workspace } from "@/components/workspace";
import { saveSessionCookie } from "@/lib/session-cookie";

function SessionInner({ id }: { id: string }) {
  const starter = useSearchParams().get("starter") ?? undefined;
  useEffect(() => saveSessionCookie(id), [id]);
  return <Workspace activeId={id} initialInput={starter} />;
}

export function SessionClient({ id }: { id: string }) {
  // useSearchParams needs a Suspense boundary (Next 16).
  return (
    <Suspense>
      <SessionInner id={id} />
    </Suspense>
  );
}
