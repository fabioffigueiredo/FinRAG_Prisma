"""Guardrail de escopo: o Prisma explica resultados; não recomenda nem prevê."""
import re

_PADROES = [
    r"devo\s+(comprar|vender|investir|aplicar|resgatar)",
    r"recomend",
    r"previs[aã]o",
    r"vai\s+(subir|cair|render)",
    r"melhor\s+(fundo|investimento|aplica[cç][aã]o)\s+para",
    r"o\s+que\s+(comprar|vender)",
    r"vale\s+a\s+pena\s+(investir|comprar|aplicar)",
]
_RX = re.compile("|".join(_PADROES), re.IGNORECASE)

INSTRUCAO_ESCOPO = (
    "\n\nImportante: você explica resultados passados com base no contexto. "
    "Não faça recomendação de compra/venda nem previsão de mercado."
)

RESPOSTA_ESCOPO = (
    "Posso explicar de onde veio o resultado do fundo e o que os números "
    "significam, mas não faço recomendação de investimento nem previsão de "
    "mercado — o Prisma é explicativo por design. Reformule perguntando sobre "
    "o desempenho observado (ex.: \"de onde veio o retorno no período?\")."
)


def pede_recomendacao(texto: str) -> bool:
    return bool(_RX.search(texto or ""))
