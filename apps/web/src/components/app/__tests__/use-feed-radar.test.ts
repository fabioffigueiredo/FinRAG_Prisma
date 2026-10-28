import { describe, expect, it } from "vitest";
import { haQuanto } from "@/components/app/use-feed-radar";

describe("haQuanto", () => {
  const agora = new Date("2026-10-28T12:00:00Z").getTime();

  it("mostra 'agora' para menos de um minuto", () => {
    expect(haQuanto("2026-10-28T11:59:40Z", agora)).toBe("agora");
  });

  it("usa minutos abaixo de uma hora", () => {
    expect(haQuanto("2026-10-28T11:48:00Z", agora)).toBe("há 12 min");
  });

  it("usa horas a partir de uma hora", () => {
    expect(haQuanto("2026-10-28T09:00:00Z", agora)).toBe("há 3 h");
  });

  it("nunca mostra tempo negativo para relógio adiantado da fonte", () => {
    expect(haQuanto("2026-10-28T12:05:00Z", agora)).toBe("agora");
  });
});
