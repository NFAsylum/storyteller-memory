"use client";

import { Download } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";

const FORMATS: { format: "markdown" | "txt" | "json"; label: string }[] = [
  { format: "markdown", label: "Markdown (.md) — chat com headings" },
  { format: "txt", label: "Texto (.txt) — só a narração" },
  { format: "json", label: "JSON (.json) — dump completo" },
];

export function ExportDialog({ sessionId }: { sessionId: string }) {
  return (
    <Dialog>
      <DialogTrigger
        className={buttonVariants({ variant: "outline", size: "sm", className: "h-7 gap-1 text-xs" })}
        aria-label="exportar história"
      >
        <Download className="size-3.5" /> Export
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Exportar história</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          {FORMATS.map((f) => (
            <a
              key={f.format}
              href={api.exportUrl(sessionId, f.format)}
              download
              className={buttonVariants({
                variant: "secondary",
                size: "sm",
                className: "w-full justify-start",
              })}
            >
              {f.label}
            </a>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
