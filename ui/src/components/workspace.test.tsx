import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Workspace } from "./workspace";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("@/lib/hooks", () => ({ useSessions: () => ({ data: [], isLoading: false }) }));

describe("Workspace", () => {
  it("colapsa e reexibe a sidebar pelo toggle (em qualquer tamanho)", async () => {
    render(<Workspace activeId={null} />);
    expect(screen.getByText("Sessões")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "esconder sessões" }));
    expect(screen.queryByText("Sessões")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "mostrar sessões" }));
    expect(screen.getByText("Sessões")).toBeInTheDocument();
  });
});
