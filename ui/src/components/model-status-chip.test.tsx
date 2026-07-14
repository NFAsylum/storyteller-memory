import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ModelStatusChip } from "./model-status-chip";

const mockUseHealth = vi.fn();
vi.mock("@/lib/hooks", () => ({ useHealth: () => mockUseHealth() }));

describe("ModelStatusChip", () => {
  it("shows a loading placeholder while fetching", () => {
    mockUseHealth.mockReturnValue({ data: undefined, error: undefined, isLoading: true });
    render(<ModelStatusChip />);
    expect(screen.getByText("carregando…")).toBeInTheDocument();
  });

  it("renders backend and live-detected model on success", () => {
    mockUseHealth.mockReturnValue({
      data: {
        status: "ok",
        backend_llm: "local",
        llm_model: "qwen2.5-coder-7b",
        mem0_ready: true,
        db_ready: true,
      },
      error: undefined,
      isLoading: false,
    });
    render(<ModelStatusChip />);
    expect(screen.getByText("local")).toBeInTheDocument();
    expect(screen.getByText("qwen2.5-coder-7b")).toBeInTheDocument();
    expect(screen.getByTestId("model-status-chip").getAttribute("title")).toContain(
      "Model: qwen2.5-coder-7b",
    );
  });

  it("shows an offline state when the request errors", () => {
    mockUseHealth.mockReturnValue({ data: undefined, error: new Error("boom"), isLoading: false });
    render(<ModelStatusChip />);
    expect(screen.getByText("backend offline")).toBeInTheDocument();
  });
});
