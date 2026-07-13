import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { SetupWizard } from "./setup-wizard";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/session-cookie", () => ({ saveSessionCookie: vi.fn() }));
vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    api: {
      createSession: vi.fn().mockResolvedValue({ id: "new1", name: "H", last_turn: 0, config: {} }),
      storyStarters: vi.fn().mockResolvedValue({ genre: "scifi", starters: ["Abertura sci-fi"] }),
    },
  };
});

describe("SetupWizard", () => {
  it("navega os passos e cria a sessão com a config escolhida", async () => {
    render(<SetupWizard />);
    await userEvent.click(screen.getByRole("button", { name: "Nova" }));

    await userEvent.type(screen.getByLabelText("nome da história"), "Minha saga");
    await userEvent.click(screen.getByRole("button", { name: "Sci-fi" }));
    await userEvent.click(screen.getByRole("button", { name: "Próximo" })); // -> voice
    await userEvent.click(screen.getByRole("button", { name: "Próximo" })); // -> protagonist
    await userEvent.click(screen.getByRole("button", { name: "Próximo" })); // -> starters (async)

    const create = await screen.findByRole("button", { name: "Criar história" });
    await userEvent.click(create);

    await waitFor(() =>
      expect(api.createSession).toHaveBeenCalledWith(
        "Minha saga",
        "",
        expect.objectContaining({ genre: "scifi" }),
      ),
    );
  });
});
