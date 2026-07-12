import { render, screen } from "@testing-library/react";
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
});
