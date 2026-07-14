"""Camada de reconciliação (Meta 2) — valida se a soma das contribuições
bate com o retorno da cota, com mensagem EXPLICÁVEL em vez de stack trace.

Decidi devolver um objeto com mensagem legível, em vez de levantar
`ValueError` como o sistema real faz ("abra um incidente no GTI"), porque
notei no diagnóstico que a dor do analista é justamente ter que cruzar uma
tabela crua manualmente — aqui pelo menos aponto causas prováveis.
"""
from __future__ import annotations

from dataclasses import dataclass

CAUSAS_PROVAVEIS = (
    "ativo sem estratégia classificada (verifique EstrategiaVersao vigente)",
    "lançamento contábil fora da janela do período",
    "erro na base de posição/peso médio",
)


@dataclass(frozen=True)
class ResultadoBatimento:
    ok: bool
    divergencia_pp: float
    mensagem: str


def validar_batimento(soma_contribuicoes_pp: float, retorno_cota_pp: float, *,
                      tolerancia_pp: float = 0.01, contexto: str = "") -> ResultadoBatimento:
    """`contexto` é opcional (ex.: "ALFA-33 · 2º trimestre 2026") — entra na
    mensagem pra facilitar localizar o problema quando chamado em lote."""
    divergencia_pp = round(soma_contribuicoes_pp - retorno_cota_pp, 4)
    ok = abs(divergencia_pp) <= tolerancia_pp

    if ok:
        mensagem = (
            f"Batimento OK: soma das contribuições ({soma_contribuicoes_pp:.2f}pp) "
            f"bate com o retorno da cota ({retorno_cota_pp:.2f}pp)."
        )
        return ResultadoBatimento(ok=True, divergencia_pp=divergencia_pp, mensagem=mensagem)

    sinal = "acima" if divergencia_pp > 0 else "abaixo"
    prefixo = f"Divergência de batimento em {contexto}: " if contexto else "Divergência de batimento: "
    mensagem = (
        f"{prefixo}a soma das contribuições ({soma_contribuicoes_pp:.2f}pp) fica "
        f"{abs(divergencia_pp):.2f}pp {sinal} do retorno da cota ({retorno_cota_pp:.2f}pp) — "
        f"acima da tolerância de {tolerancia_pp:.2f}pp. Causas prováveis: "
        + "; ".join(CAUSAS_PROVAVEIS) + "."
    )
    return ResultadoBatimento(ok=False, divergencia_pp=divergencia_pp, mensagem=mensagem)
