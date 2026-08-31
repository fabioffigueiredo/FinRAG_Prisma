import { beforeEach, describe, expect, it, vi } from "vitest";

const response = vi.hoisted(() => ({
  next: vi.fn(() => ({ kind: "next" })),
  redirect: vi.fn((url: URL) => ({ kind: "redirect", url: url.toString() })),
}));

vi.mock("next/server", () => ({
  NextResponse: response,
}));

import { proxy } from "./proxy";

function request(pathname: string, session = false) {
  const url = new URL(`https://wiki.ioi.ia.br/prisma${pathname}`);
  return {
    nextUrl: {
      pathname,
      clone: () => new URL(url),
    },
    cookies: { has: () => session },
  } as never;
}

describe("proxy", () => {
  beforeEach(() => {
    response.next.mockClear();
    response.redirect.mockClear();
  });

  it("mantém a demonstração pública acessível sem sessão", () => {
    expect(proxy(request("/demonstracao"))).toEqual({ kind: "next" });
    expect(response.redirect).not.toHaveBeenCalled();
  });

  it("continua protegendo uma rota da aplicação sem sessão", () => {
    expect(proxy(request("/radar"))).toMatchObject({ kind: "redirect" });
    expect(response.redirect).toHaveBeenCalledOnce();
  });
});
