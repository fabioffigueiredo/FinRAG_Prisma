"""Prisma Sinais v0 — alerta probabilístico de apoio à decisão (NUNCA recomendação).

Desenho de governança (ver docs/GOVERNANCA_IA.md):
- Quem estima é um MODELO TRANSPARENTE DE REGRAS (esta função), não a LLM.
- Saída sempre com: probabilidade, base de cálculo, evidências e aviso legal.
- v0 = regras documentadas abaixo (dados fictícios do POC); v1 (piloto) = modelo
  estatístico backtestado na base real, com hit-rate publicado na tela.

Regras v0 (documentadas e determinísticas):
  prob_neg = clamp(48 - 28*sentimento_liquido + penalidade_contrib, 5, 95)
    - sentimento_liquido em [-1, 1] vem do radar (notícias por estratégia);
    - penalidade_contrib = +7 se a contribuição corrente da estratégia < 0;
  nível: alerta se prob_neg >= 60 · atenção se >= 45 · ok abaixo disso.
"""
from __future__ import annotations

MODELO_VERSAO = "sinais-v0 (regras transparentes)"

AVISO_LEGAL = (
    "Sinal probabilístico de APOIO À DECISÃO, gerado por modelo de regras "
    "auditável sobre dados do período. NÃO constitui recomendação de compra ou "
    "venda, análise de valores mobiliários (Res. CVM 20) ou garantia de resultado. "
    "Uso interno; a decisão é sempre do gestor."
)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


_ESTRATEGIA_GERAL = "Mercado Geral"


def gerar_sinais(fundo: dict, agregado: dict, noticias: list[dict]) -> list[dict]:
    """Gera sinais por estratégia do fundo a partir do sentimento do radar.

    Decidi cair pro agregado de "Mercado Geral" quando a estratégia não tem
    notícia própria porque notei que o radar ao vivo (RSS real) não sabe
    classificar uma manchete por estratégia do fundo — sem esse fallback,
    NENHUMA estratégia batia mais (todas as notícias reais caem em "Mercado
    Geral") e o sinal ficava sempre vazio. Marco `fonte_geral` pra não fingir
    que é evidência específica da estratégia.
    """
    out = []
    geral = agregado.get(_ESTRATEGIA_GERAL)
    for e in fundo.get("estrategias", []):
        nome = e["nome"]
        g = agregado.get(nome)
        fonte_geral = False
        if not g or not g.get("total"):
            if geral and geral.get("total"):
                g, fonte_geral = geral, True
            else:
                continue  # sem notícia específica nem geral -> sem sinal (não inventar)
        sent = float(g.get("liquido", 0.0))
        contrib = float(e.get("contribuicao_pp", 0.0))
        prob_neg = _clamp(48 - 28 * sent + (7 if contrib < 0 else 0), 5, 95)
        nivel = "alerta" if prob_neg >= 60 else ("atencao" if prob_neg >= 45 else "ok")
        chave_evidencia = _ESTRATEGIA_GERAL if fonte_geral else nome
        evidencias = [f"noticia:{n['id']}" for n in noticias if n.get("estrategia") == chave_evidencia]
        base = "regras v0: 48 - 28xsentimento + 7 se contribuicao<0 (clamp 5-95)"
        if fonte_geral:
            base += " — sem notícia específica da estratégia; usado sentimento de mercado geral"
        out.append({
            "estrategia": nome,
            "nivel": nivel,
            "prob_neg": round(prob_neg),
            "sentimento_liquido": sent,
            "noticias_no_periodo": g["total"],
            "contribuicao_pp": contrib,
            "evidencias": evidencias,
            "fonte_geral": fonte_geral,
            "base_calculo": base,
            "validacao": "v0 sem backtest — validacao estatistica entra no piloto (v1)",
            "modelo_versao": MODELO_VERSAO,
        })
    out.sort(key=lambda s: -s["prob_neg"])
    return out
