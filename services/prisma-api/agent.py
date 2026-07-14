"""Agente de análise conversacional do Prisma: traduz pergunta em linguagem
natural para chamadas de ferramenta sobre os dados do fundo (POC sobre o seed;
na integração real as mesmas ferramentas viram chamadas HTTP à plataforma de
atribuição — ver ROTEIRO/plano). O LLM planeja e narra; nunca calcula números.
"""
from __future__ import annotations

import json
import re

DIMENSOES_VALIDAS = [
    "estrategia", "grupo_contabil", "supergrupo", "vencimento",
    "privados", "renda_variavel", "renda_fixa", "ativos",
]
DIMENSOES_LABEL = {
    "estrategia": "Estratégia", "grupo_contabil": "Grupo Contábil",
    "supergrupo": "Supergrupo", "vencimento": "Vencimento", "privados": "Privados",
    "renda_variavel": "Renda Variável", "renda_fixa": "Renda Fixa", "ativos": "Ativos",
}
_ALIASES_DIMENSAO = {
    "grupo contábil": "grupo_contabil", "grupo contabil": "grupo_contabil",
    "rv": "renda_variavel", "rf": "renda_fixa", "renda variável": "renda_variavel",
    "renda fixa": "renda_fixa",
}
_ALIASES_FUNDO = {"alfa": "ALFA-33", "beta": "BETA-71", "gama": "GAMA-12"}

SISTEMA_AGENTE = (
    "Você é o Prisma, copiloto de atribuição de performance para gestores de fundos. "
    "Responda SOMENTE com base nos dados retornados pelas ferramentas — nunca invente "
    "números, datas ou nomes de estratégia. Sempre que a pergunta envolver retorno, "
    "contribuição por estratégia/grupo, comparação com benchmark ou evolução no tempo, "
    "chame a ferramenta apropriada antes de responder; use resolver_fundo primeiro se o "
    "usuário mencionar o fundo por nome. Depois de obter os dados, escreva um parágrafo "
    "curto e objetivo em português explicando o resultado, citando os números retornados "
    "e mencionando qualquer aviso da ferramenta. Não recomende compra/venda nem faça "
    "previsão de mercado."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "resolver_fundo",
            "description": (
                "Resolve o nome mencionado pelo usuário para o código interno do fundo "
                "(ex.: 'Alfa' -> 'ALFA-33'). Use antes das outras ferramentas quando o "
                "fundo for citado por nome."
            ),
            "parameters": {
                "type": "object",
                "properties": {"nome": {"type": "string", "description": "Nome ou apelido do fundo citado pelo usuário"}},
                "required": ["nome"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obter_atribuicao",
            "description": (
                "Retorna a contribuição de cada estratégia/grupo para o retorno do fundo e "
                "o resumo do resultado (retorno, benchmark, alpha, beta). Use para 'de onde "
                "veio o retorno', 'contribuição por estratégia/grupo contábil', 'comparação "
                "com benchmark'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fundo": {"type": "string", "description": "Código do fundo (ex. ALFA-33)"},
                    "dimensao": {"type": "string", "enum": DIMENSOES_VALIDAS,
                                 "description": "Dimensão de agregação pedida pelo usuário"},
                    "periodo": {"type": "string", "description": "Período citado pelo usuário, texto livre (ex. '2T26')"},
                    "benchmark": {"type": "string", "description": "Benchmark citado pelo usuário (ex. 'CDI', 'Ibovespa')"},
                    "top_n": {"type": "integer", "description": "Limitar aos N maiores contribuidores, se pedido"},
                },
                "required": ["fundo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obter_serie",
            "description": (
                "Retorna a série diária de retorno acumulado da cota vs benchmark, para "
                "montar um gráfico de linha. Use para 'evolução no tempo', 'gráfico de "
                "retorno', 'desempenho ao longo do período'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fundo": {"type": "string"},
                    "benchmark": {"type": "string", "description": "Benchmark a comparar"},
                },
                "required": ["fundo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obter_resumo",
            "description": (
                "Retorna só os KPIs do fundo (retorno, alpha, beta, volatilidade, "
                "patrimônio), sem decomposição. Use para perguntas diretas sem pedido de "
                "detalhamento."
            ),
            "parameters": {
                "type": "object",
                "properties": {"fundo": {"type": "string"}},
                "required": ["fundo"],
            },
        },
    },
]


def _match_fundo(fundos: dict, nome: str) -> str | None:
    nome_low = (nome or "").strip().lower()
    if not nome_low:
        return None
    for cod in fundos:
        if cod.lower() == nome_low:
            return cod
    for alias, cod in _ALIASES_FUNDO.items():
        if alias in nome_low and cod in fundos:
            return cod
    for cod, f in fundos.items():
        if nome_low in f["fundo"]["nome"].lower():
            return cod
    return None


def _detectar_fundo_citado(pergunta: str, fundos: dict) -> str | None:
    """Resolução determinística: se a pergunta citar um fundo explicitamente
    (código ou alias, com fronteira de palavra), retorna o código — tem
    prioridade sobre o 'fundo em foco' da tela ativa, para o agente não
    responder sobre o fundo errado quando o usuário nomeia outro."""
    texto = (pergunta or "").lower()
    for cod in fundos:
        if re.search(rf"\b{re.escape(cod.lower())}\b", texto):
            return cod
    for alias, cod in _ALIASES_FUNDO.items():
        if cod in fundos and re.search(rf"\b{re.escape(alias)}\b", texto):
            return cod
    for cod, f in fundos.items():
        primeira_palavra = f["fundo"]["nome"].split()[0].lower()
        if len(primeira_palavra) > 3 and re.search(rf"\b{re.escape(primeira_palavra)}\b", texto):
            return cod
    return None


def _resolver_dimensao(valor: str | None) -> str:
    if not valor:
        return "estrategia"
    v = valor.strip().lower()
    v = _ALIASES_DIMENSAO.get(v, v.replace(" ", "_"))
    return v if v in DIMENSOES_VALIDAS else "estrategia"


def _resolver_periodo(fundo_data: dict, periodo_pedido: str | None) -> tuple[str, bool]:
    """No POC só existe 1 período por fundo (seed) — sinaliza divergência em vez de inventar."""
    disponivel = fundo_data["fundo"]["periodo"]
    if not periodo_pedido:
        return disponivel, False
    bate = periodo_pedido.strip().lower() in disponivel.lower() or disponivel.lower() in periodo_pedido.strip().lower()
    return disponivel, not bate


def _resolver_benchmark(fundo_data: dict, benchmark_pedido: str | None) -> tuple[str, bool]:
    disponivel = fundo_data["fundo"]["benchmark"]
    if not benchmark_pedido:
        return disponivel, False
    return disponivel, benchmark_pedido.strip().lower() != disponivel.strip().lower()


def _tool_resolver_fundo(fundos: dict, args: dict) -> dict:
    cod = _match_fundo(fundos, args.get("nome", ""))
    return {"codigo": cod} if cod else {"erro": f"fundo '{args.get('nome')}' não encontrado"}


def _tool_obter_atribuicao(fundos: dict, args: dict) -> dict:
    cod = _match_fundo(fundos, args.get("fundo", "")) or args.get("fundo")
    f = fundos.get(cod)
    if not f:
        return {"erro": f"fundo '{args.get('fundo')}' não encontrado"}
    dimensao = _resolver_dimensao(args.get("dimensao"))
    periodo, periodo_diverge = _resolver_periodo(f, args.get("periodo"))
    benchmark, bench_diverge = _resolver_benchmark(f, args.get("benchmark"))
    estrategias = f["estrategias"]
    top_n = args.get("top_n")
    if isinstance(top_n, int) and top_n > 0:
        estrategias = sorted(estrategias, key=lambda e: abs(e["contribuicao_pp"]), reverse=True)[:top_n]

    avisos = []
    if dimensao != "estrategia":
        avisos.append(
            f"Dimensão '{DIMENSOES_LABEL.get(dimensao, dimensao)}' ainda não está disponível "
            "na base de demonstração — mostrando por Estratégia (na integração real, essa "
            "dimensão vem diretamente da plataforma de atribuição)."
        )
        dimensao = "estrategia"
    if periodo_diverge:
        avisos.append(f"Período disponível na demo: {periodo}.")
    if bench_diverge:
        avisos.append(f"Benchmark configurado do fundo: {benchmark}.")

    return {
        "fundo": cod, "nome_fundo": f["fundo"]["nome"], "periodo": periodo,
        "benchmark": benchmark, "dimensao": dimensao, "dimensao_label": DIMENSOES_LABEL[dimensao],
        "resumo": f["resumo"], "estrategias": estrategias,
        "aviso": " ".join(avisos) if avisos else None,
    }


def _tool_obter_serie(fundos: dict, args: dict) -> dict:
    cod = _match_fundo(fundos, args.get("fundo", "")) or args.get("fundo")
    f = fundos.get(cod)
    if not f:
        return {"erro": f"fundo '{args.get('fundo')}' não encontrado"}
    benchmark, bench_diverge = _resolver_benchmark(f, args.get("benchmark"))
    aviso = f"Benchmark configurado do fundo: {benchmark}." if bench_diverge else None
    return {
        "fundo": cod, "nome_fundo": f["fundo"]["nome"], "benchmark": benchmark,
        "serie": f["serie_diaria"], "aviso": aviso,
    }


def _tool_obter_resumo(fundos: dict, args: dict) -> dict:
    cod = _match_fundo(fundos, args.get("fundo", "")) or args.get("fundo")
    f = fundos.get(cod)
    if not f:
        return {"erro": f"fundo '{args.get('fundo')}' não encontrado"}
    return {
        "fundo": cod, "nome_fundo": f["fundo"]["nome"], "resumo": f["resumo"],
        "periodo": f["fundo"]["periodo"], "benchmark": f["fundo"]["benchmark"],
    }


def _tool_dispatch(nome: str, args: dict, fundos: dict) -> dict:
    if nome == "resolver_fundo":
        return _tool_resolver_fundo(fundos, args)
    if nome == "obter_atribuicao":
        return _tool_obter_atribuicao(fundos, args)
    if nome == "obter_serie":
        return _tool_obter_serie(fundos, args)
    if nome == "obter_resumo":
        return _tool_obter_resumo(fundos, args)
    return {"erro": f"ferramenta desconhecida: {nome}"}


def _bloco_grafico(nome_tool: str, out: dict) -> dict | None:
    if "erro" in out:
        return None
    if nome_tool == "obter_atribuicao":
        return {
            "tipo": "grafico", "chart": "waterfall",
            "titulo": f"Atribuição por {out['dimensao_label']} — {out['nome_fundo']}",
            "dados": {
                "estrategias": out["estrategias"],
                "total": out["resumo"]["retorno_cota"],
                "benchmark": out["resumo"]["retorno_bench"],
                "benchLabel": out["benchmark"],
            },
        }
    if nome_tool == "obter_serie":
        return {
            "tipo": "grafico", "chart": "linha",
            "titulo": f"Retorno acumulado vs {out['benchmark']} — {out['nome_fundo']}",
            "dados": {"serie": out["serie"]},
        }
    if nome_tool == "obter_resumo":
        return {
            "tipo": "kpis", "chart": None,
            "titulo": f"Resumo — {out['nome_fundo']}",
            "dados": {"resumo": out["resumo"]},
        }
    return None


def _gerar_acoes(consulta_echo: dict) -> list[dict]:
    fundo = consulta_echo.get("fundo") or ""
    return [
        {"label": "Comparar Benchmarks", "prompt": f"Compare o {fundo} com o Ibovespa e o IMA-B"},
        {"label": "Ver por Grupo Contábil", "prompt": f"Mostre a atribuição do {fundo} por grupo contábil"},
        {"label": "Evolução no período", "prompt": f"Mostre o gráfico de evolução do {fundo} no período"},
        {"label": "Exportar Relatório", "prompt": "__exportar_pdf__"},
    ]


def analisar(*, pergunta: str, fundo_ativo: str, backend, fundos: dict, max_turns: int = 4) -> dict:
    """Loop de agente com tool-calling. `backend` é um cliente com .chat(messages, tools, temperature)."""
    blocos: list[dict] = []
    consulta_echo: dict = {}
    avisos: list[str] = []
    tool_trace: list[dict] = []
    resposta = ""

    # Detecção determinística (não o LLM): se a pergunta citar outro fundo,
    # isso tem prioridade sobre o fundo em foco na tela.
    fundo_citado = _detectar_fundo_citado(pergunta, fundos)
    if fundo_citado and fundo_citado != fundo_ativo:
        contexto_fundo = (
            f"[fundo em foco na tela: {fundo_ativo}; mas esta pergunta cita outro fundo "
            f"({fundo_citado}) — use {fundo_citado}, IGNORE o fundo em foco] {pergunta}"
        )
    else:
        contexto_fundo = f"[fundo em foco: {fundo_ativo}] {pergunta}"

    messages = [
        {"role": "system", "content": SISTEMA_AGENTE},
        {"role": "user", "content": contexto_fundo},
    ]

    for _ in range(max_turns):
        result = backend.chat(messages, tools=TOOLS, temperature=0.1)
        if not result["tool_calls"]:
            resposta = result["content"].strip()
            break
        # Formato genérico (arguments como dict) — cada client traduz para seu wire format:
        # Groq/OpenAI quer arguments como string JSON; Ollama quer objeto puro.
        messages.append({
            "role": "assistant",
            "content": result["content"] or "",
            "tool_calls": [
                {"id": tc["id"], "name": tc["name"], "arguments": tc["arguments"]}
                for tc in result["tool_calls"]
            ],
        })
        for tc in result["tool_calls"]:
            out = _tool_dispatch(tc["name"], tc["arguments"], fundos)
            tool_trace.append({"tool": tc["name"], "args": tc["arguments"]})
            if tc["name"] in ("obter_atribuicao", "obter_serie", "obter_resumo") and "erro" not in out:
                consulta_echo.setdefault("fundo", out.get("fundo"))
                if out.get("periodo"):
                    consulta_echo["periodo"] = out["periodo"]
                if out.get("benchmark"):
                    consulta_echo["benchmark"] = out["benchmark"]
                if out.get("dimensao_label"):
                    consulta_echo["dimensao"] = out["dimensao_label"]
                if out.get("aviso"):
                    avisos.append(out["aviso"])
                bloco = _bloco_grafico(tc["name"], out)
                if bloco:
                    blocos.append(bloco)
            messages.append({
                "role": "tool", "tool_call_id": tc["id"],
                "content": json.dumps(out, ensure_ascii=False),
            })
    else:
        resposta = "Não consegui concluir a análise dentro do limite de passos — tente reformular a pergunta."

    return {
        "resposta": resposta, "consulta_echo": consulta_echo, "blocos": blocos,
        "acoes": _gerar_acoes(consulta_echo), "avisos": avisos, "tool_trace": tool_trace,
    }


def analisar_mock(*, fundo_ativo: str, fundos: dict, pergunta: str = "") -> dict:
    """Caminho determinístico para o motor Demo (sem tool-calling): chama a tool
    diretamente e narra com texto fixo, para o modo Demo nunca quebrar."""
    fundo_citado = _detectar_fundo_citado(pergunta, fundos)
    fundo_alvo = fundo_citado or fundo_ativo
    out = _tool_obter_atribuicao(fundos, {"fundo": fundo_alvo})
    if "erro" in out:
        return {"resposta": out["erro"], "consulta_echo": {}, "blocos": [], "acoes": [], "avisos": [], "tool_trace": []}
    bloco = _bloco_grafico("obter_atribuicao", out)
    top3 = "; ".join(f"{e['nome']} {e['contribuicao_pp']:+.2f}pp" for e in out["estrategias"][:3])
    resposta = (
        f"(Demonstração) O {out['nome_fundo']} teve retorno de {out['resumo']['retorno_cota']:.2f}% "
        f"no período, ante {out['resumo']['retorno_bench']:.2f}% do {out['benchmark']} — excesso de "
        f"{out['resumo']['excesso_pp']:+.2f} pp. Principais contribuições: {top3}."
    )
    consulta_echo = {"fundo": out["fundo"], "periodo": out["periodo"], "benchmark": out["benchmark"],
                      "dimensao": out["dimensao_label"]}
    return {
        "resposta": resposta, "consulta_echo": consulta_echo, "blocos": [bloco] if bloco else [],
        "acoes": _gerar_acoes(consulta_echo), "avisos": [out["aviso"]] if out.get("aviso") else [],
        "tool_trace": [],
    }
