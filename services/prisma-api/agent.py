"""Agente de análise conversacional do Prisma: traduz pergunta em linguagem
natural para chamadas de ferramenta sobre os dados do fundo (POC sobre o seed;
na integração real as mesmas ferramentas viram chamadas HTTP à plataforma de
atribuição — ver ROTEIRO/plano). O LLM planeja e narra; nunca calcula números.
"""
from __future__ import annotations

import json
import re

from sinais import gerar_sinais, AVISO_LEGAL as SINAIS_AVISO_LEGAL
from radar import agregar as agregar_noticias

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
_ALIASES_FUNDO = {"alfa": "ALFA-33", "beta": "BETA-71", "gama": "GAMA-12", "eta": "ETA-27"}
# "eta" tem só 3 letras — abaixo do limiar len>3 do heurístico primeira_palavra
# de _detectar_fundo_citado, então precisa de alias explícito pra ser
# reconhecido em texto livre (mesmo motivo por que alfa/beta/gama já estavam
# aqui em vez de confiar só no heurístico).
# Palavras genéricas demais para servir de "apelido" de um fundo no laço
# primeira_palavra de _detectar_fundo_citado — "fundo"/"fundos" é a colisão
# que motivou isto (fixtures de teste nomeiam fundos como "Fundo {codigo}",
# então a palavra genérica "fundo" numa pergunta batia com qualquer fundo);
# fic/fim/fia são sufixos comuns de estrutura de fundo brasileiro, igualmente
# não-distintivos (ver plans/006-avisar-fundo-nao-reconhecido-no-mock.md).
_PALAVRAS_GENERICAS_NOME = {"fundo", "fundos", "fic", "fim", "fia"}

SISTEMA_AGENTE = (
    "Você é o Prisma, copiloto de atribuição de performance para gestores de fundos. "
    "Responda SOMENTE com base nos dados retornados pelas ferramentas — nunca invente "
    "números, datas ou nomes de estratégia. Sempre que a pergunta envolver retorno, "
    "contribuição por estratégia/grupo, comparação com benchmark ou evolução no tempo, "
    "chame a ferramenta apropriada antes de responder; use resolver_fundo primeiro se o "
    "usuário mencionar o fundo por nome. Se a pergunta for sobre mudança/evolução entre "
    "períodos ('o que mudou', 'comparado ao trimestre passado'), use comparar_periodos. "
    "Se a pergunta for sobre indicação, sinal ou notícia de mercado para o fundo/estratégia, "
    "use obter_sinais_mercado — nunca infira sinal de mercado sem chamar essa ferramenta, e "
    "sempre inclua o aviso legal retornado por ela na resposta. "
    "Depois de obter os dados, escreva um parágrafo "
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
    {
        "type": "function",
        "function": {
            "name": "comparar_periodos",
            "description": (
                "Compara o período mais recente com o anterior do mesmo fundo: quanto o "
                "retorno da cota mudou e quais estratégias/grupos mais subiram ou caíram de "
                "contribuição. Use para 'o que mudou desde o trimestre passado', 'evolução "
                "entre períodos', 'comparar com o período anterior'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fundo": {"type": "string"},
                    "dimensao": {"type": "string", "enum": DIMENSOES_VALIDAS,
                                 "description": "Dimensão de agregação a comparar (padrão: estratégia)"},
                },
                "required": ["fundo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obter_sinais_mercado",
            "description": (
                "Retorna o alerta probabilístico de risco por estratégia do fundo, "
                "calculado por um modelo de regras transparente sobre o sentimento das "
                "notícias do radar de mercado (nível, probabilidade, evidências citadas "
                "por id de notícia, aviso legal). NUNCA é recomendação de compra/venda "
                "nem previsão — é um sinal de apoio à decisão. Use para 'qual a indicação "
                "do mercado', 'tem algum sinal de risco', 'o que as notícias dizem sobre "
                "esse fundo/estratégia', 'probabilidade desse fundo cair'."
            ),
            "parameters": {
                "type": "object",
                "properties": {"fundo": {"type": "string", "description": "Código do fundo (ex. ALFA-33)"}},
                "required": ["fundo"],
            },
        },
    },
]


def _match_fundo(fundos: dict, nome: str, indice_semantico=None) -> str | None:
    """Resolve nome -> código. Decidi deixar a busca semântica como ÚLTIMO
    recurso (só quando código exato/alias/substring falham) porque notei que
    ela é probabilística — prefiro sempre o match determinístico quando ele
    existe, e só cair pra "parecido" quando não sobra outra opção (ex.:
    'fundo de crédito privado' ou um nome digitado com erro)."""
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
    if indice_semantico is not None:
        resultados = indice_semantico.search(nome, k=1)
        if resultados:
            chunk, score = resultados[0]
            if score >= 0.3 and chunk.source in fundos:
                return chunk.source
    return None


def construir_indice_semantico_fundos(fundos: dict, embed_fn=None):
    """Constrói um índice semântico (FinRAG `SemanticIndex`, já vendorizado
    neste pacote) sobre nome/classe/benchmark de cada fundo — pra resolver
    buscas por significado ('fundo de crédito privado', nome com erro de
    digitação) em vez de exigir código exato ou substring literal do nome,
    a dor #1 encontrada no sistema real (busca só por código/nome exato)."""
    from finrag.corpus import Chunk
    from finrag.embeddings import SemanticIndex
    chunks = [
        Chunk(doc_id=cod, chunk_id=0,
             text=f"{f['fundo']['nome']} {f['fundo'].get('classe', '')} benchmark {f['fundo'].get('benchmark', '')}",
             source=cod)
        for cod, f in fundos.items()
    ]
    indice = SemanticIndex(embed_fn=embed_fn)
    indice.build(chunks)
    return indice


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
        if (len(primeira_palavra) > 3 and primeira_palavra not in _PALAVRAS_GENERICAS_NOME
                and re.search(rf"\b{re.escape(primeira_palavra)}\b", texto)):
            return cod
    return None


_PADRAO_CODIGO_FUNDO = re.compile(r"\b[A-Za-zÀ-ú]{2,10}-\d{1,4}\b")


def _fundo_nao_reconhecido_citado(pergunta: str, fundos: dict) -> str | None:
    """Se a pergunta menciona algo no formato de código de fundo
    (LETRAS-NÚMERO, ex. 'XYZ-99') que não bate com nenhum fundo conhecido,
    devolve esse texto em maiúsculas — pra `analisar_mock` avisar o usuário
    em vez de responder silenciosamente sobre outro fundo (ver
    plans/006-avisar-fundo-nao-reconhecido-no-mock.md)."""
    for m in _PADRAO_CODIGO_FUNDO.finditer(pergunta or ""):
        candidato = m.group(0).upper()
        if candidato not in fundos:
            return candidato
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


def _obter_contribuicoes_db(fundo_codigo: str, periodo_label: str, dimensao: str) -> list[dict]:
    """Tenta buscar a dimensão no Postgres da Meta 1/2; devolve lista vazia
    (nunca levanta) se o banco não estiver configurado/alcançável — mesmo
    princípio de degradação graciosa do resto do código (Ollama/Groq/RSS):
    o copiloto não pode quebrar por causa de uma dependência opcional."""
    try:
        from db.repo import obter_contribuicoes_dimensao
        from db.session import SessionLocal
        db = SessionLocal()
        try:
            return obter_contribuicoes_dimensao(db, fundo_codigo, periodo_label, dimensao)
        finally:
            db.close()
    except Exception:
        return []


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
        dados_db = _obter_contribuicoes_db(cod, periodo, dimensao)
        if dados_db:
            estrategias = dados_db
            if isinstance(top_n, int) and top_n > 0:
                estrategias = sorted(estrategias, key=lambda e: abs(e["contribuicao_pp"]), reverse=True)[:top_n]
        else:
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


def _tool_obter_sinais_mercado(fundos: dict, noticias: list[dict], args: dict) -> dict:
    cod = _match_fundo(fundos, args.get("fundo", "")) or args.get("fundo")
    f = fundos.get(cod)
    if not f:
        return {"erro": f"fundo '{args.get('fundo')}' não encontrado"}
    if not noticias:
        return {"fundo": cod, "nome_fundo": f["fundo"]["nome"], "sinais": [],
                "aviso": "Radar de notícias sem dados no momento — sem base para gerar sinal.",
                "aviso_legal": SINAIS_AVISO_LEGAL}
    sinais = gerar_sinais(f, agregar_noticias(noticias), noticias)
    return {"fundo": cod, "nome_fundo": f["fundo"]["nome"], "sinais": sinais,
            "aviso_legal": SINAIS_AVISO_LEGAL}


def _tool_comparar_periodos(fundos: dict, args: dict) -> dict:
    cod = _match_fundo(fundos, args.get("fundo", "")) or args.get("fundo")
    f = fundos.get(cod)
    if not f:
        return {"erro": f"fundo '{args.get('fundo')}' não encontrado"}
    dimensao = _resolver_dimensao(args.get("dimensao"))
    try:
        from db.repo import comparar_periodos_dimensao
        from db.session import SessionLocal
        db = SessionLocal()
        try:
            comparacao = comparar_periodos_dimensao(db, cod, dimensao)
        finally:
            db.close()
    except Exception:
        comparacao = None

    if comparacao is None:
        return {
            "fundo": cod, "nome_fundo": f["fundo"]["nome"],
            "erro": (
                "Comparação entre períodos ainda não está disponível na base de "
                "demonstração — precisa de pelo menos 2 períodos carregados com essa "
                "dimensão (na integração real, isso vem do histórico da plataforma)."
            ),
        }
    comparacao["fundo"] = cod
    comparacao["nome_fundo"] = f["fundo"]["nome"]
    return comparacao


def _tool_dispatch(nome: str, args: dict, fundos: dict, noticias: list[dict]) -> dict:
    if nome == "resolver_fundo":
        return _tool_resolver_fundo(fundos, args)
    if nome == "obter_atribuicao":
        return _tool_obter_atribuicao(fundos, args)
    if nome == "obter_serie":
        return _tool_obter_serie(fundos, args)
    if nome == "obter_resumo":
        return _tool_obter_resumo(fundos, args)
    if nome == "comparar_periodos":
        return _tool_comparar_periodos(fundos, args)
    if nome == "obter_sinais_mercado":
        return _tool_obter_sinais_mercado(fundos, noticias, args)
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
    if nome_tool == "obter_sinais_mercado":
        return None  # sinal é texto narrado, sem bloco de gráfico dedicado (Meta atual)
    return None


def _gerar_acoes(consulta_echo: dict) -> list[dict]:
    fundo = consulta_echo.get("fundo") or ""
    return [
        {"label": "Comparar Benchmarks", "prompt": f"Compare o {fundo} com o Ibovespa e o IMA-B"},
        {"label": "Ver por Grupo Contábil", "prompt": f"Mostre a atribuição do {fundo} por grupo contábil"},
        {"label": "Evolução no período", "prompt": f"Mostre o gráfico de evolução do {fundo} no período"},
        {"label": "Sinais de Mercado", "prompt": f"Qual a indicação de mercado para o {fundo}?"},
        {"label": "Exportar Relatório", "prompt": "__exportar_pdf__"},
    ]


def analisar(*, pergunta: str, fundo_ativo: str, backend, fundos: dict, noticias: list[dict], max_turns: int = 4) -> dict:
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
            out = _tool_dispatch(tc["name"], tc["arguments"], fundos, noticias)
            tool_trace.append({"tool": tc["name"], "args": tc["arguments"]})
            if tc["name"] in ("obter_atribuicao", "obter_serie", "obter_resumo",
                             "comparar_periodos") and "erro" not in out:
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


_PALAVRAS_SINAL = ("sinal", "sinais", "indicaç", "notícia", "noticia", "mercado", "risco")
_PALAVRAS_EVOLUCAO = ("evoluç", "gráfico", "grafico", "linha do tempo", "ao longo do")
_PALAVRAS_GRUPO_CONTABIL = ("grupo contábil", "grupo contabil")


def analisar_mock(*, fundo_ativo: str, fundos: dict, noticias: list[dict] | None = None, pergunta: str = "") -> dict:
    """Caminho determinístico para o motor Demo (sem tool-calling): NÃO chama
    LLM, mas escolhe a tool certa por palavra-chave da pergunta — pra não
    devolver a mesma narrativa de atribuição pra qualquer pergunta (ver
    plans/002-copiloto-sinais-mercado-e-degradado-visivel.md, achado
    original: motor Demo respondia igual pra 'rentabilidade' e 'indicação
    de mercado')."""
    noticias = noticias or []
    fundo_citado = _detectar_fundo_citado(pergunta, fundos)
    if not fundo_citado:
        nao_reconhecido = _fundo_nao_reconhecido_citado(pergunta, fundos)
        if nao_reconhecido:
            return {"resposta": f"(Demonstração) Fundo '{nao_reconhecido}' não encontrado — "
                                f"verifique o código e tente novamente.",
                    "consulta_echo": {}, "blocos": [], "acoes": [], "avisos": [], "tool_trace": []}
    fundo_alvo = fundo_citado or fundo_ativo
    pergunta_low = (pergunta or "").lower()

    if any(p in pergunta_low for p in _PALAVRAS_SINAL):
        out = _tool_obter_sinais_mercado(fundos, noticias, {"fundo": fundo_alvo})
        if "erro" in out:
            return {"resposta": out["erro"], "consulta_echo": {}, "blocos": [], "acoes": [], "avisos": [], "tool_trace": []}
        if not out["sinais"]:
            resposta = (
                f"(Demonstração) Sem sinal de mercado disponível para {out['nome_fundo']} no momento "
                f"— {out.get('aviso', 'radar sem notícias suficientes')}. {SINAIS_AVISO_LEGAL}"
            )
        else:
            pior = out["sinais"][0]  # já vem ordenado por -prob_neg (maior risco primeiro)
            resposta = (
                f"(Demonstração) Para {out['nome_fundo']}, o sinal de maior atenção é em "
                f"{pior['estrategia']}: nível {pior['nivel']}, probabilidade de contribuição "
                f"negativa {pior['prob_neg']}% ({pior['base_calculo']}). {SINAIS_AVISO_LEGAL}"
            )
        consulta_echo = {"fundo": out["fundo"]}
        return {"resposta": resposta, "consulta_echo": consulta_echo, "blocos": [],
                "acoes": _gerar_acoes(consulta_echo), "avisos": [], "tool_trace": []}

    if any(p in pergunta_low for p in _PALAVRAS_EVOLUCAO):
        out = _tool_obter_serie(fundos, {"fundo": fundo_alvo})
        if "erro" in out:
            return {"resposta": out["erro"], "consulta_echo": {}, "blocos": [], "acoes": [], "avisos": [], "tool_trace": []}
        bloco = _bloco_grafico("obter_serie", out)
        resposta = f"(Demonstração) Evolução de {out['nome_fundo']} vs {out['benchmark']} no período — ver gráfico."
        consulta_echo = {"fundo": out["fundo"], "benchmark": out["benchmark"]}
        return {"resposta": resposta, "consulta_echo": consulta_echo, "blocos": [bloco] if bloco else [],
                "acoes": _gerar_acoes(consulta_echo), "avisos": [out["aviso"]] if out.get("aviso") else [], "tool_trace": []}

    dimensao_args = {"fundo": fundo_alvo}
    if any(p in pergunta_low for p in _PALAVRAS_GRUPO_CONTABIL):
        dimensao_args["dimensao"] = "grupo_contabil"
    out = _tool_obter_atribuicao(fundos, dimensao_args)
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
    return {"resposta": resposta, "consulta_echo": consulta_echo, "blocos": [bloco] if bloco else [],
            "acoes": _gerar_acoes(consulta_echo), "avisos": [out["aviso"]] if out.get("aviso") else [], "tool_trace": []}
