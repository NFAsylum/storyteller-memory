import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Workspace } from "./workspace";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("@/lib/hooks", () => ({ useSessions: () => ({ data: [], isLoading: false }) }));

describe("Workspace (responsivo)", () => {
  it("abre e fecha o drawer da sidebar pelo botão mobile", async () => {
    render(<Workspace activeId={null} />);
    expect(screen.queryByTestId("sidebar-overlay")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "abrir sessões" }));
    expect(screen.getByTestId("sidebar-overlay")).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("sidebar-overlay"));
    expect(screen.queryByTestId("sidebar-overlay")).not.toBeInTheDocument();
  });
});
