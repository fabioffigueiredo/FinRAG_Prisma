import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
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
const listarGestorasPublico = vi.fn();

vi.mock("@/lib/api", () => ({
  getCsrf: (...args: unknown[]) => getCsrf(...args),
  login: (...args: unknown[]) => login(...args),
  loginMicrosoftDemo: (...args: unknown[]) => loginMicrosoftDemo(...args),
  verificar2fa: (...args: unknown[]) => verificar2fa(...args),
  listarGestorasPublico: (...args: unknown[]) => listarGestorasPublico(...args),
}));

/** Base UI Select — abre o trigger e clica na opção pelo texto (achado #15:
 * login agora pede gestora pra desambiguar matrícula, que não é mais única
 * globalmente). */
async function selecionarGestora(nome: string) {
  // Espera a lista de gestoras (fetch assíncrono no useEffect) terminar de
  // carregar ANTES de abrir o combobox — abrir com a lista ainda vazia faz
  // o Base UI Select montar o listbox sem itens, e a opção nunca aparece
  // depois (a Collection só é coletada na montagem do popup).
  await waitFor(() => expect(listarGestorasPublico).toHaveBeenCalled());
  await new Promise((resolve) => setTimeout(resolve, 0));
  fireEvent.click(screen.getByRole("combobox", { name: /gestora/i }));
  fireEvent.click(await screen.findByRole("option", { name: nome }));
}

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

describe("LoginPage", () => {
  beforeEach(() => {
    push.mockClear();
    refresh.mockClear();
    getCsrf.mockClear();
    login.mockReset();
    loginMicrosoftDemo.mockReset();
    verificar2fa.mockReset();
    listarGestorasPublico.mockReset();
    listarGestorasPublico.mockResolvedValue({ ok: true, gestoras: [{ id: 1, nome: "Gestora Demo" }] });
  });

  it("mantém o botão Entrar desabilitado enquanto os campos estão vazios", () => {
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: "Entrar" })).toBeDisabled();
  });

  it("habilita o botão quando gestora, matrícula e senha estão preenchidos", async () => {
    render(<LoginPage />);
    await selecionarGestora("Gestora Demo");
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
    await selecionarGestora("Gestora Demo");
    fireEvent.change(screen.getByLabelText(/matrícula/i), { target: { value: "DEMO-001" } });
    fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "errada" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("matrícula ou senha inválidas")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("redireciona para a rota 'from' após login bem-sucedido", async () => {
    login.mockResolvedValue({ ok: true, nome: "Ana Demo", papel: "gestor", gestora_id: 1 });
    render(<LoginPage />);
    await selecionarGestora("Gestora Demo");
    fireEvent.change(screen.getByLabelText(/matrícula/i), { target: { value: "DEMO-001" } });
    fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "demo12345" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    expect(refresh).toHaveBeenCalled();
    expect(login).toHaveBeenCalledWith(1, "DEMO-001", "demo12345");
  });
});
