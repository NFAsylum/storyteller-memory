import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MemoryInspector } from "./memory-inspector";

vi.mock("@/lib/hooks", () => ({
  useMemoryState: () => ({
    data: {
      characters: [
        { id: 1, name: "Aria", traits: ["leal", "corajosa"], first_appeared_turn: 1, last_seen_turn: 3 },
      ],
      locations: [{ name: "Aldrath", description: "castelo", first_visited_turn: 1 }],
      relations: [],
      story_beats: [{ summary: "Aria descobre a traição", turn: 3, importance: 8, tags: [] }],
    },
  }),
}));

describe("MemoryInspector", () => {
  it("mostra as contagens por aba e o card do personagem", () => {
    render(<MemoryInspector sessionId="a" />);
    expect(screen.getByText("Personagens (1)")).toBeInTheDocument();
    expect(screen.getByText("Locais (1)")).toBeInTheDocument();
    expect(screen.getByText("Beats (1)")).toBeInTheDocument();

    expect(screen.getByTestId("character-card")).toHaveTextContent("Aria");
    expect(screen.getByText("leal")).toBeInTheDocument();
  });

  it("troca para a aba Locais e revela o local (painel inativo desmontado)", async () => {
    render(<MemoryInspector sessionId="a" />);
    // Base UI desmonta o painel inativo — o local não está no DOM antes do clique.
    expect(screen.queryByText("Aldrath")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Locais/ }));
    expect(await screen.findByText("Aldrath")).toBeInTheDocument();
  });
});
