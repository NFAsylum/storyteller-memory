import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Hero } from "./hero";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/session-cookie", () => ({ saveSessionCookie: vi.fn() }));

describe("Hero", () => {
  it("mostra o pitch e abre o 'como funciona'", async () => {
    render(<Hero onDismiss={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Storyteller" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Como funciona" }));
    expect(await screen.findByText("Como a memória funciona")).toBeInTheDocument();
  });

  it("'Explorar sessões' chama onDismiss", async () => {
    const onDismiss = vi.fn();
    render(<Hero onDismiss={onDismiss} />);
    await userEvent.click(screen.getByRole("button", { name: "Explorar sessões" }));
    expect(onDismiss).toHaveBeenCalled();
  });
});
