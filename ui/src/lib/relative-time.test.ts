import { describe, expect, it } from "vitest";

import { relativeTime } from "./relative-time";

const NOW = new Date("2026-07-13T12:00:00Z").getTime();
const ago = (ms: number) => new Date(NOW - ms).toISOString();

describe("relativeTime", () => {
  it("mostra 'agora' para poucos segundos", () => {
    expect(relativeTime(ago(10_000), NOW)).toBe("agora");
  });
  it("minutos", () => {
    expect(relativeTime(ago(5 * 60_000), NOW)).toBe("5 min atrás");
  });
  it("horas", () => {
    expect(relativeTime(ago(3 * 3_600_000), NOW)).toBe("3 h atrás");
  });
  it("ontem e dias", () => {
    expect(relativeTime(ago(24 * 3_600_000), NOW)).toBe("ontem");
    expect(relativeTime(ago(3 * 24 * 3_600_000), NOW)).toBe("3 dias atrás");
  });
});
