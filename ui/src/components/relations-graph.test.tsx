import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RelationsGraph } from "./relations-graph";

const characters = [
  { id: 1, name: "Aria", traits: [], first_appeared_turn: 1, last_seen_turn: 5 },
  { id: 2, name: "Vex", traits: [], first_appeared_turn: 2, last_seen_turn: 4 },
];
const relations = [
  { id: 10, a_character_id: 1, b_character_id: 2, kind: "enemy", valence: -2, since_turn: 3 },
];

describe("RelationsGraph", () => {
  it("renderiza nós e a legenda quando há relações", () => {
    render(<RelationsGraph characters={characters} relations={relations} />);
    expect(screen.getByTestId("relations-graph")).toBeInTheDocument();
    expect(screen.getAllByTestId("graph-node")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /enemy/ })).toBeInTheDocument(); // legend + filter
  });

  it("mostra empty state informativo sem relações", () => {
    render(<RelationsGraph characters={characters} relations={[]} />);
    expect(screen.queryByTestId("relations-graph")).not.toBeInTheDocument();
    expect(screen.getByText(/Nenhuma relação identificada/)).toBeInTheDocument();
  });

  it("filtra por tipo ao clicar na legenda", async () => {
    render(<RelationsGraph characters={characters} relations={relations} />);
    const svg = screen.getByTestId("relations-graph");
    expect(svg.querySelectorAll("line")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: /enemy/ }));
    expect(svg.querySelectorAll("line")).toHaveLength(0); // hidden kind removes the edge
  });

  it("click no nó pede scroll do chat para o turno do personagem", async () => {
    const handler = vi.fn();
    window.addEventListener("storyteller:scroll-to-turn", handler);
    render(<RelationsGraph characters={characters} relations={relations} />);
    await userEvent.click(screen.getAllByTestId("graph-node")[0]); // Aria (last_seen desc)
    expect((handler.mock.calls[0][0] as CustomEvent).detail).toBe(1); // Aria first_appeared_turn
    window.removeEventListener("storyteller:scroll-to-turn", handler);
  });
});
