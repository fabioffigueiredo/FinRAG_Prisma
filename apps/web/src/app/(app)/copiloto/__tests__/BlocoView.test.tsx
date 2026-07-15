/**
 * Meta 4 — regressão do bug real achado nesta branch: os gráficos do
 * copiloto (Waterfall/PerformanceLine) não apareciam no chat porque
 * `BlocoView` os renderizava sem nenhum ancestral com altura definida
 * (`h-full` resolvia contra 0px). O fix foi envolver cada gráfico num
 * container com altura fixa — este teste garante que isso não regride.
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { BlocoView } from "../page";
import type { BlocoGrafico } from "@/lib/api";

const blocoWaterfall: BlocoGrafico = {
  tipo: "grafico",
  chart: "waterfall",
  titulo: "Atribuição por Estratégia — Alfa",
  dados: {
    estrategias: [
      { nome: "Crédito Privado", contribuicao_pp: 1.35, peso_medio: 28, cor: "gold" },
      { nome: "Juros Brasil", contribuicao_pp: 1.05, peso_medio: 24, cor: "blue" },
    ],
    total: 4.25,
    benchmark: 3.10,
    benchLabel: "CDI",
  },
};

const blocoLinha: BlocoGrafico = {
  tipo: "grafico",
  chart: "linha",
  titulo: "Evolução — Alfa",
  dados: {
    serie: [
      { data: "2026-04-01", cota: 0, bench: 0 },
      { data: "2026-04-02", cota: 0.5, bench: 0.3 },
    ],
  },
};

const blocoKpis: BlocoGrafico = {
  tipo: "kpis",
  chart: null,
  titulo: "Resumo — Alfa",
  dados: {
    resumo: { retorno_cota: 4.25, excesso_pp: 1.15, alpha_pp: 1.10, beta: 0.15 },
  },
};

describe("BlocoView", () => {
  it("envolve o waterfall num container com altura fixa (h-[300px])", () => {
    const { container } = render(<BlocoView bloco={blocoWaterfall} />);
    expect(container.querySelector(".h-\\[300px\\]")).not.toBeNull();
  });

  it("envolve o gráfico de linha num container com altura fixa (h-[240px])", () => {
    const { container } = render(<BlocoView bloco={blocoLinha} />);
    expect(container.querySelector(".h-\\[240px\\]")).not.toBeNull();
  });

  it("renderiza os KPIs sem precisar de container de altura (usa grid)", () => {
    const { getByText } = render(<BlocoView bloco={blocoKpis} />);
    expect(getByText("Retorno")).toBeInTheDocument();
    expect(getByText("Alpha")).toBeInTheDocument();
  });

  it("mostra o título do bloco", () => {
    const { getByText } = render(<BlocoView bloco={blocoWaterfall} />);
    expect(getByText("Atribuição por Estratégia — Alfa")).toBeInTheDocument();
  });
});
