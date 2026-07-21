"""Guardrail de escopo: o Prisma explica resultados; não recomenda nem prevê."""
import re

_PADROES = [
    r"devo\s+(comprar|vender|investir|aplicar|resgatar|sair|entrar|aportar)",
    r"recomend",
    r"previs[aã]o",
    r"vai\s+(subir|cair|render)",
    r"melhor\s+(fundo|investimento|aplica[cç][aã]o)\s+(para|pra)",
    r"o\s+que\s+(eu\s+)?(compr(ar|o|a)|vend(er|o|e))",
    r"(vale\s+a\s+pena|compensa)\s+(investir|comprar|aplicar|resgatar|sair|vender)",
    r"bom\s+momento\s+(para|pra)\s+(comprar|vender|resgatar|sair|entrar)",
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


# Guardrail de injeção/vazamento na PERGUNTA do usuário (além do de documentos).
_PADROES_INJECAO = [
    r"ignore?\s+(as\s+)?(instru[cç][oõ]es|regras)",
    r"desconsidere\s+(as\s+)?(instru[cç][oõ]es|regras)",
    r"esque[cç]a\s+(as\s+)?(instru[cç][oõ]es|regras)",
    r"instru[cç][oõ]es\s+anteriores",
    r"(revele|mostre|imprima|repita|exiba)\s+.{0,20}(prompt|instru[cç][oõ]es|regras|sistema)",
    r"prompt\s+do\s+sistema",
    r"system\s+prompt",
    r"aja\s+como|finja\s+ser|voc[eê]\s+agora\s+[eé]",
    r"jailbreak|dev\s*mode|modo\s+desenvolvedor",
]
_RX_INJ = re.compile("|".join(_PADROES_INJECAO), re.IGNORECASE)

RESPOSTA_INJECAO = (
    "Essa solicitação foi bloqueada pelo guardrail: não revelo instruções de "
    "sistema nem altero meu escopo. Sigo explicando o resultado do fundo com "
    "base nas fontes citadas. Reformule perguntando sobre o desempenho observado."
)


def tenta_injecao(texto: str) -> bool:
    return bool(_RX_INJ.search(texto or ""))
