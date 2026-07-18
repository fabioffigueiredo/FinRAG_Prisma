import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PasswordInput } from "../password-input";

describe("PasswordInput", () => {
  it("começa oculto (type=password)", () => {
    render(<PasswordInput aria-label="senha" />);
    expect(screen.getByLabelText("senha")).toHaveAttribute("type", "password");
  });

  it("alterna pra texto visível ao clicar no olho, e volta a ocultar no 2º clique", () => {
    render(<PasswordInput aria-label="senha" />);
    const campo = screen.getByLabelText("senha");
    const botao = screen.getByRole("button", { name: "Mostrar senha" });

    fireEvent.click(botao);
    expect(campo).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Ocultar senha" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ocultar senha" }));
    expect(campo).toHaveAttribute("type", "password");
  });
});
