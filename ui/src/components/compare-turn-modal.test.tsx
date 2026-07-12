import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { CompareTurnModal } from "./compare-turn-modal";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() } }));

vi.mock("@/lib/api", () => ({
  api: {
    compareTurn: vi.fn().mockResolvedValue({
      user_input: "Aria confronta Vex",
      no_memory: { narrator: "Resposta genérica sem contexto.", retrieved: null },
      mem0_only: { narrator: "Aria, lembrando da traição, confronta Vex.", retrieved: {} },
    }),
  },
}));

describe("CompareTurnModal", () => {
  it("abre o split-screen com as duas respostas", async () => {
    render(<CompareTurnModal sessionId="a" />);
    await userEvent.click(screen.getByRole("button", { name: /Comparar com\/sem memória/i }));

    await waitFor(() =>
      expect(screen.getByText("Resposta genérica sem contexto.")).toBeInTheDocument(),
    );
    expect(screen.getByText("Aria, lembrando da traição, confronta Vex.")).toBeInTheDocument();
  });

  it("mostra toast de erro e não exibe respostas quando a comparação falha", async () => {
    vi.mocked(api.compareTurn).mockRejectedValueOnce(new Error("500"));
    render(<CompareTurnModal sessionId="a" />);
    await userEvent.click(screen.getByRole("button", { name: /Comparar com\/sem memória/i }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.queryByText("Resposta genérica sem contexto.")).not.toBeInTheDocument();
  });
});
