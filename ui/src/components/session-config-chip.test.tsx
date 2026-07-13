import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SessionConfigChip } from "./session-config-chip";

vi.mock("@/lib/hooks", () => ({
  useSession: () => ({
    data: {
      id: "a",
      config: {
        genre: "horror",
        pov: "first_person",
        tone: "gothic",
        content_intensity: "sfw",
        target_length: "medium",
        protagonist: { role: "author", character_name: "", character_role: "" },
      },
    },
  }),
}));

describe("SessionConfigChip", () => {
  it("mostra o resumo da config e abre o modal de edição", async () => {
    render(<SessionConfigChip sessionId="a" />);
    expect(screen.getByText(/Horror · First person · Gothic/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "editar controles da história" }));
    expect(await screen.findByText("Controles da história")).toBeInTheDocument();
  });
});
