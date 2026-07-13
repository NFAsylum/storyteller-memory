import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { ChatArea } from "./chat-area";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/session-cookie", () => ({ saveSessionCookie: vi.fn() }));

vi.mock("@/lib/hooks", () => ({
  useSession: () => ({
    data: {
      id: "a",
      turns: [
        {
          turn_number: 1,
          user_input: "Aria chega",
          narrator_text: "A porta range.",
          created_at: "2026-07-13T00:00:00Z",
        },
      ],
      last_turn: 1,
    },
    isLoading: false,
  }),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    api: {
      runTurn: vi.fn().mockResolvedValue({}),
      editTurn: vi.fn().mockResolvedValue({}),
      regenerateTurn: vi.fn().mockResolvedValue({}),
      deleteTurn: vi.fn().mockResolvedValue(undefined),
      forkSession: vi.fn().mockResolvedValue({ id: "b", name: "x", last_turn: 1 }),
      exportUrl: (id: string, fmt: string) => `http://x/sessions/${id}/export?format=${fmt}`,
    },
  };
});

describe("ChatArea", () => {
  it("renderiza os turnos existentes", () => {
    render(<ChatArea sessionId="a" />);
    expect(screen.getByText("Aria chega")).toBeInTheDocument();
    expect(screen.getByText("A porta range.")).toBeInTheDocument();
  });

  it("envia um novo turno pela API", async () => {
    render(<ChatArea sessionId="a" />);
    await userEvent.type(screen.getByLabelText("entrada do turno"), "Aria avança");
    await userEvent.click(screen.getByRole("button", { name: "Próximo turno" }));
    await waitFor(() => expect(api.runTurn).toHaveBeenCalledWith("a", "Aria avança"));
  });

  it("mostra toast de erro quando o turno falha (sem crash)", async () => {
    vi.mocked(api.runTurn).mockRejectedValueOnce(new Error("timeout"));
    render(<ChatArea sessionId="a" />);
    await userEvent.type(screen.getByLabelText("entrada do turno"), "Aria cai");
    await userEvent.click(screen.getByRole("button", { name: "Próximo turno" }));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("timeout")),
    );
  });

  it("edita um turno e re-narra", async () => {
    render(<ChatArea sessionId="a" />);
    await userEvent.click(screen.getByLabelText("editar turno 1"));
    const editor = screen.getByLabelText("editar entrada do turno");
    await userEvent.clear(editor);
    await userEvent.type(editor, "Aria recua");
    await userEvent.click(screen.getByRole("button", { name: "Salvar e re-narrar" }));
    await waitFor(() => expect(api.editTurn).toHaveBeenCalledWith("a", 1, "Aria recua"));
  });

  it("regenera um turno", async () => {
    render(<ChatArea sessionId="a" />);
    await userEvent.click(screen.getByLabelText("regenerar turno 1"));
    await waitFor(() => expect(api.regenerateTurn).toHaveBeenCalledWith("a", 1));
  });
});
