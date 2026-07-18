import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "../page";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
  useSearchParams: () => new URLSearchParams(),
}));

const getCsrf = vi.fn().mockResolvedValue("csrf-fake");
const login = vi.fn();
const loginMicrosoftDemo = vi.fn();
const verificar2fa = vi.fn();

vi.mock("@/lib/api", () => ({
  getCsrf: (...args: unknown[]) => getCsrf(...args),
  login: (...args: unknown[]) => login(...args),
  loginMicrosoftDemo: (...args: unknown[]) => loginMicrosoftDemo(...args),
  verificar2fa: (...args: unknown[]) => verificar2fa(...args),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    push.mockClear();
    refresh.mockClear();
    getCsrf.mockClear();
    login.mockReset();
    loginMicrosoftDemo.mockReset();
    verificar2fa.mockReset();
  });

  it("mantém o botão Entrar desabilitado enquanto os campos estão vazios", () => {
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: "Entrar" })).toBeDisabled();
  });

  it("habilita o botão quando matrícula e senha estão preenchidas", () => {
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/matrícula/i), { target: { value: "DEMO-001" } });
    fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "demo12345" } });
    expect(screen.getByRole("button", { name: "Entrar" })).toBeEnabled();
  });

  it("busca o token CSRF ao montar (bootstrap do login-CSRF)", () => {
    render(<LoginPage />);
    expect(getCsrf).toHaveBeenCalledTimes(1);
  });

  it("mostra a mensagem genérica de erro devolvida pela API, sem indicar qual campo errou", async () => {
    login.mockResolvedValue({ ok: false, erro: "matrícula ou senha inválidas" });
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/matrícula/i), { target: { value: "DEMO-001" } });
    fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "errada" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("matrícula ou senha inválidas")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("redireciona para a rota 'from' após login bem-sucedido", async () => {
    login.mockResolvedValue({ ok: true, nome: "Ana Demo", papel: "gestor", gestora_id: 1 });
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/matrícula/i), { target: { value: "DEMO-001" } });
    fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "demo12345" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    expect(refresh).toHaveBeenCalled();
  });
});
