import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { ChatArea } from "./chat-area";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() } }));

vi.mock("@/lib/hooks", () => ({
  useSession: () => ({
    data: {
      id: "a",
      turns: [{ turn_number: 1, user_input: "Aria chega", narrator_text: "A porta range." }],
      last_turn: 1,
    },
    isLoading: false,
  }),
}));
vi.mock("@/lib/api", () => ({ api: { runTurn: vi.fn().mockResolvedValue({}) } }));

describe("ChatArea", () => {
  it("renderiza os turnos existentes", () => {
    render(<ChatArea sessionId="a" />);
    expect(screen.getByText("Aria chega")).toBeInTheDocument();
    expect(screen.getByText("A porta range.")).toBeInTheDocument();
  });

  it("envia um novo turno pela API", async () => {
    render(<ChatArea sessionId="a" />);
    await userEvent.type(screen.getByLabelText("entrada do turno"), "Aria avança");
    await userEvent.click(screen.getByRole("button", { name: "Próximo turno" }));
    await waitFor(() => expect(api.runTurn).toHaveBeenCalledWith("a", "Aria avança"));
  });

  it("mostra toast de erro quando o turno falha (sem crash)", async () => {
    vi.mocked(api.runTurn).mockRejectedValueOnce(new Error("timeout"));
    render(<ChatArea sessionId="a" />);
    await userEvent.type(screen.getByLabelText("entrada do turno"), "Aria cai");
    await userEvent.click(screen.getByRole("button", { name: "Próximo turno" }));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("timeout")),
    );
  });
});
