import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CompareTurnModal } from "./compare-turn-modal";

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
});
