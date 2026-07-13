import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ExportDialog } from "./export-dialog";

describe("ExportDialog", () => {
  it("oferece download nos 3 formatos com os hrefs certos", async () => {
    render(<ExportDialog sessionId="abc" />);
    await userEvent.click(screen.getByRole("button", { name: "exportar história" }));

    const md = await screen.findByRole("link", { name: /Markdown/ });
    expect(md).toHaveAttribute("href", expect.stringContaining("/sessions/abc/export?format=markdown"));
    expect(screen.getByRole("link", { name: /Texto/ })).toHaveAttribute(
      "href",
      expect.stringContaining("format=txt"),
    );
    expect(screen.getByRole("link", { name: /JSON/ })).toHaveAttribute(
      "href",
      expect.stringContaining("format=json"),
    );
  });
});
