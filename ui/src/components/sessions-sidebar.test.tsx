import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionsSidebar } from "./sessions-sidebar";

const mock = vi.hoisted(() => ({ sessions: { data: [] as unknown[], isLoading: false } }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("@/lib/hooks", () => ({ useSessions: () => mock.sessions }));

beforeEach(() => {
  mock.sessions = {
    data: [
      { id: "a", name: "História A", last_turn: 3, created_at: "2026-07-11T00:00:00" },
      { id: "b", name: "História B", last_turn: 0, created_at: "2026-07-11T00:00:00" },
    ],
    isLoading: false,
  };
});

describe("SessionsSidebar", () => {
  it("lista as sessões e destaca a ativa", () => {
    render(<SessionsSidebar activeId="a" />);
    expect(screen.getByText("História A")).toBeInTheDocument();
    expect(screen.getByText("História B")).toBeInTheDocument();

    const items = screen.getAllByTestId("session-item");
    expect(items).toHaveLength(2);
    expect(items[0].className).toContain("font-medium"); // a ativa (id "a")
    expect(items[0]).toHaveAttribute("href", "/sessions/a");
  });

  it("mostra o estado vazio quando não há sessões", () => {
    mock.sessions = { data: [], isLoading: false };
    render(<SessionsSidebar activeId={null} />);
    expect(screen.getByText("Nenhuma sessão ainda.")).toBeInTheDocument();
    expect(screen.queryAllByTestId("session-item")).toHaveLength(0);
  });
});
