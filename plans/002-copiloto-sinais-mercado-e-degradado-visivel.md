# Plan 002: Conectar sinais de mercado ao copiloto e tornar respostas degradadas visíveis/auditáveis

> **Executor instructions**: Siga este plano passo a passo. Rode cada comando
> de verificação e confirme o resultado esperado antes do próximo passo. Se
> algo na seção "STOP conditions" ocorrer, pare e reporte — não improvise.
> Ao terminar, atualize a linha de status deste plano em `plans/README.md`
> (a menos que quem te despachou tenha dito que cuida do índice).
>
> **Drift check (rode primeiro)**: `git diff --stat d0cb607..HEAD -- services/prisma-api/agent.py services/prisma-api/llm.py services/prisma-api/app.py services/prisma-api/sinais.py services/prisma-api/radar.py apps/web/src/app/\(app\)/copiloto/page.tsx apps/web/src/lib/api.ts`
> Se algum desses arquivos mudou desde que este plano foi escrito, compare os
> trechos de "Estado atual" abaixo com o código ao vivo antes de prosseguir;
> em caso de divergência, trate como condição de STOP.
>
> **Aviso sobre a árvore de trabalho**: no momento em que este plano foi
> escrito, a árvore de trabalho tinha mudanças NÃO commitadas e SEM RELAÇÃO
> com este plano em `services/prisma-api/app.py`, `auth.py`, `db/models.py` e
> arquivos de teste de autenticação (correções de uma revisão de código
> anterior, sobre 2FA/cadastro/convite — nada em `agent.py`, `llm.py`,
> `sinais.py`, `radar.py` ou no copiloto). Se você está rodando isto numa
> worktree isolada (fluxo `execute`), isso não te afeta — a worktree parte
> limpa do SHA travado. Se está rodando direto na árvore de trabalho do
> operador, rode `git status` primeiro e NÃO misture essas mudanças alheias
> no seu commit; se `app.py` já estiver modificado por outro motivo, aplique
> suas edições por cima e commit só o diff que você introduziu (`git add -p`
> se precisar separar).

## Status

- **Priority**: P0 (itens 1–4) / P1 (item 5) — ver detalhamento por passo
- **Effort**: M
- **Risk**: LOW (aditivo — nova tool, novo campo em payload já declarado no
  tipo TS, novo ramo de UI; não remove nem muda comportamento de nada que já
  funciona)
- **Depends on**: none
- **Category**: bug + tech-debt + direction (copiloto genuinamente inteligente) + docs (conformidade com `docs/GOVERNANCA_IA.md`)
- **Planned at**: commit `d0cb607`, 2026-07-20

## Por que isso importa

Um gestor de fundos testou manualmente o "Pergunte ao Prisma"
(`wiki.ioi.ia.br/prisma/copiloto`) e observou, verbalizando ao vivo: pergunta
"qual a indicação do mercado para esse fundo?" e recebe a MESMA narrativa de
atribuição por estratégia que já tinha recebido pra "qual foi a
rentabilidade do fundo no semestre?" — sem nenhuma menção a notícia, sinal ou
radar de mercado. A suspeita dele, nas próprias palavras: "verifique se ele
está respondendo aleatoriamente, só com respostas programadas, ou se ele
está guardando informações."

A investigação (nesta sessão, por leitura de código — não é audit de
subagente, é leitura direta linha por linha dos arquivos citados abaixo)
confirma a suspeita com precisão: **o caminho que respondeu no vídeo
(`analisar_mock`) SEMPRE chama a mesma tool de atribuição, não importa a
pergunta** — ele só extrai do texto QUAL FUNDO está sendo citado, nunca QUE
TIPO de pergunta foi feita. E mesmo o caminho real com LLM+tool-calling
(`analisar`) **não tem nenhuma tool que acesse notícia, radar ou sinal de
mercado** — só 5 tools, todas sobre atribuição/série/resumo/comparação de
período. Ou seja: mesmo com um LLM de verdade conectado, o copiloto hoje é
estruturalmente incapaz de responder "qual a indicação do mercado", porque a
ferramenta pra isso não existe no agente — apesar de o produto JÁ TER um
motor de sinal de mercado completo, determinístico e auditável
(`sinais.py::gerar_sinais`, com testes cobrindo, ver `tests/test_sinais.py`)
alimentando a tela "Sinais" separadamente, sem nenhuma ligação com o chat.

Isso é agravado por dois problemas de transparência: (1) o backend já
calcula corretamente se a resposta veio do LLM real ou do fallback
determinístico (`degradado: bool`, `app.py`), mas **o frontend nunca lê esse
campo** — o banner "Resposta fundamentada apenas nos dados consultados ·
guardrail ativo" é uma string estática, idêntica nos dois casos, então um
gestor não tem como saber, olhando a tela, se está vendo uma análise real ou
um texto enlatado; (2) o mesmo campo `degradado` **não é gravado na trilha de
auditoria** (`audit.registrar` na rota `/analisar` não inclui esse campo),
violando o espírito do próprio `docs/GOVERNANCA_IA.md` §5
("Rastreabilidade e auditoria") — depois do fato, um compliance não consegue
saber, olhando o log, se uma resposta histórica foi gerada de verdade ou
era texto de demonstração.

O que este plano NÃO muda (por design, documentado, não é bug): o guardrail
de escopo que recusa pedido de recomendação de compra/venda
(`pede_recomendacao`, ver `docs/GOVERNANCA_IA.md` §1, base na Resolução CVM
20) continua recusando — o plano inclui um teste de regressão pra isso
continuar assim, não pra afrouxar.

## Estado atual

Arquivos relevantes, cada um com seu papel:

- `services/prisma-api/agent.py` — agente do copiloto: lista de tools
  (`TOOLS`), prompt de sistema (`SISTEMA_AGENTE`), dispatch de tool
  (`_tool_dispatch`), loop real com LLM (`analisar`), fallback determinístico
  pro motor Demo (`analisar_mock`), geração dos botões de ação sugerida
  (`_gerar_acoes`).
- `services/prisma-api/sinais.py` — já existe e já é testado
  (`tests/test_sinais.py`, 6 testes passando). `gerar_sinais(fundo, agregado,
  noticias) -> list[dict]` devolve, por estratégia do fundo: `nivel`
  (`ok`/`atencao`/`alerta`), `prob_neg`, `sentimento_liquido`,
  `noticias_no_periodo`, `contribuicao_pp`, `evidencias` (lista de
  `"noticia:<id>"`), `fonte_geral` (bool), `base_calculo` (string
  explicando a fórmula), `validacao`, `modelo_versao`. Constantes
  `AVISO_LEGAL` e `MODELO_VERSAO` no mesmo módulo.
- `services/prisma-api/radar.py` — `carregar_noticias(path)` e
  `agregar(noticias)` (agrega sentimento por estratégia); é o que já
  alimenta a tela Radar de Mercado com RSS real.
- `services/prisma-api/app.py`:
  - `STATE: dict = {"index": None, "embed": "?", "fundos": None, "noticias":
    None}` (linha ~114) — estado em memória do processo; `STATE["noticias"]`
    é populado no startup via `radar.carregar_noticias(NOTICIAS_PATH)`
    (linha ~163).
  - `GET /sinais` (linhas 970-979) já mostra o padrão exato de como montar
    o sinal a partir do estado global:
    ```python
    @app.get("/sinais")
    def sinais_endpoint(fundo: str = "ALFA-33"):
        fundos = STATE.get("fundos") or {}
        f = fundos.get(fundo) or (next(iter(fundos.values())) if fundos else None)
        noticias = STATE.get("noticias") or []
        if not f or not noticias:
            return {"ok": False, "sinais": [], "aviso": AVISO_LEGAL, "modelo": MODELO_VERSAO}
        sinais = gerar_sinais(f, agregar(noticias), noticias)
        return {"ok": True, "sinais": sinais, "aviso": AVISO_LEGAL, "modelo": MODELO_VERSAO}
    ```
  - `class AnalisarReq(BaseModel)` (linha ~179): `pergunta: str`, `backend:
    str = "ollama"`, `fundo: str = "ALFA-33"`.
  - `POST /analisar` (linhas 879-934) — rota do copiloto:
    ```python
    fundos = STATE.get("fundos") or {}
    degradado = False
    try:
        cliente = get_backend(req.backend)
        if hasattr(cliente, "chat"):
            resultado = agente.analisar(pergunta=req.pergunta, fundo_ativo=req.fundo,
                                        backend=cliente, fundos=fundos)
        else:
            resultado = agente.analisar_mock(fundo_ativo=req.fundo, fundos=fundos, pergunta=req.pergunta)
            degradado = True
    except Exception:
        resultado = agente.analisar_mock(fundo_ativo=req.fundo, fundos=fundos, pergunta=req.pergunta)
        degradado = True

    lat = int((time.perf_counter() - t0) * 1000)
    audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                    backend=req.backend, latency_ms=lat,
                    fontes=[t["tool"] for t in resultado.get("tool_trace", [])],
                    bloqueados=[], resposta=resultado["resposta"],
                    extra={"consulta_echo": resultado.get("consulta_echo"),
                           "tool_trace": resultado.get("tool_trace")})
    return {
        "resposta": resultado["resposta"], "consulta_echo": resultado.get("consulta_echo", {}),
        "blocos": resultado.get("blocos", []), "acoes": resultado.get("acoes", []),
        "avisos": resultado.get("avisos", []), "citacoes": [], "bloqueados": [],
        "backend": req.backend, "latency_ms": lat, "degradado": degradado,
    }
    ```
    Note que `extra={...}` no `audit.registrar` NÃO inclui `degradado` —
    esse é o gap de auditoria do item 4 abaixo.
  - `get_backend` vem de `services/prisma-api/llm.py:105-131`: sem
    `GROQ_API_KEY` configurada, `get_backend("groq")` devolve `MockLLM` (que
    só tem `.generate`, não `.chat`) — por isso escolher "Nuvem" na UI sem a
    chave cai, silenciosamente, no ramo `else` acima (`analisar_mock`,
    `degradado = True`). Isso é o que o vídeo mostra: motor "Nuvem"
    selecionado, toda resposta com prefixo "(Demonstração)".
- `services/prisma-api/agent.py:400-490` (íntegra relevante hoje):
  ```python
  TOOLS = [  # resolver_fundo, obter_atribuicao, obter_serie, obter_resumo, comparar_periodos — só essas 5
      ...
  ]

  def analisar(*, pergunta: str, fundo_ativo: str, backend, fundos: dict, max_turns: int = 4) -> dict:
      ...  # loop de tool-calling real — funciona, mas só tem as 5 tools acima

  def analisar_mock(*, fundo_ativo: str, fundos: dict, pergunta: str = "") -> dict:
      """Caminho determinístico para o motor Demo (sem tool-calling): chama a tool
      diretamente e narra com texto fixo, para o modo Demo nunca quebrar."""
      fundo_citado = _detectar_fundo_citado(pergunta, fundos)
      fundo_alvo = fundo_citado or fundo_ativo
      out = _tool_obter_atribuicao(fundos, {"fundo": fundo_alvo})   # <- SEMPRE esta tool, não importa a pergunta
      if "erro" in out:
          return {"resposta": out["erro"], "consulta_echo": {}, "blocos": [], "acoes": [], "avisos": [], "tool_trace": []}
      bloco = _bloco_grafico("obter_atribuicao", out)
      top3 = "; ".join(f"{e['nome']} {e['contribuicao_pp']:+.2f}pp" for e in out["estrategias"][:3])
      resposta = (
          f"(Demonstração) O {out['nome_fundo']} teve retorno de {out['resumo']['retorno_cota']:.2f}% "
          f"no período, ante {out['resumo']['retorno_bench']:.2f}% do {out['benchmark']} — excesso de "
          f"{out['resumo']['excesso_pp']:+.2f} pp. Principais contribuições: {top3}."
      )
      ...
  ```
  `_gerar_acoes` (linhas 390-397) gera os 4 botões de ação sugerida
  ("Comparar Benchmarks", "Ver por Grupo Contábil", "Evolução no período",
  "Exportar Relatório") — os prompts reenviados batem em `/analisar` de
  novo; como `analisar_mock` ignora completamente o texto da pergunta pra
  decidir QUAL tool chamar (só usa pra achar o fundo), clicar em "Evolução
  no período" no motor Demo devolve o MESMO gráfico de cascata (waterfall)
  em vez do gráfico de linha esperado — é o "não faz nada" / "mesma coisa"
  observado no teste manual.
- `apps/web/src/lib/api.ts:37-51` — tipo `AnaliseResp` já declara
  `degradado?: boolean` (o backend já manda o campo; só falta o frontend
  usar).
- `apps/web/src/app/(app)/copiloto/page.tsx`:
  - linha 327: `const bloqueado = data.bloqueados.length > 0;`
  - linhas 411-432: bloco condicional do banner — hoje só distingue
    `bloqueado` (guardrail de injeção) do caso "sucesso", nunca olha
    `degradado`:
    ```tsx
    ) : (
      <div className={cn("flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs",
        bloqueado ? "border-[var(--destructive)]/40 bg-[var(--destructive)]/10 text-[var(--destructive)]"
                  : "border-[var(--success)]/30 bg-[var(--success)]/10 text-[var(--success)]")}>
        {bloqueado ? (
          <><ShieldAlert .../>Guardrail bloqueou {data.bloqueados.length} trecho(s)...</>
        ) : (
          <><ShieldCheck .../>Resposta fundamentada apenas nos dados consultados · guardrail ativo.</>
        )}
      </div>
    )}
    ```
- Vocabulário/tokens de design a reusar (ver `apps/web/DESIGN.md`): o caso
  "fora de escopo" já usa a cor `--chart-5` como tom de aviso (âmbar) em vez
  de `--destructive` (vermelho) — use o mesmo token pro banner de
  "degradado", já que não é um erro/bloqueio, é um aviso de que a resposta
  não é a análise real.
- Testes existentes a seguir como padrão (mesma pasta
  `services/prisma-api/tests/`):
  - `test_agent_tools.py` — testa tools do agente isoladamente, importa só
    `agent`, sem HTTP:
    ```python
    import agent

    def _fundo(codigo, retorno_cota, retorno_bench, pontos_cota):
        return {
            "fundo": {"nome": f"Fundo {codigo}", "codigo": codigo, "benchmark": "CDI",
                      "periodo": "2T26", "classe": "Teste"},
            "resumo": {"retorno_cota": retorno_cota, "retorno_bench": retorno_bench,
                       "excesso_pp": round(retorno_cota - retorno_bench, 2), "pct_cdi": 0.0,
                       "beta": 0.5, "alpha_pp": round(retorno_cota - retorno_bench, 2),
                       "vol_anual": 1.0, "patrimonio_mm": 1.0, "num_cotistas": 1},
            "estrategias": [{"nome": "Caixa e Over", "contribuicao_pp": retorno_cota,
                            "peso_medio": 100.0, "cor": "neutral"}],
            "serie_diaria": [{"data": f"2026-04-{i:02d}", "cota": v, "bench": 0.0}
                             for i, v in enumerate(pontos_cota, start=1)],
            "ativos": [], "fics": [],
        }

    def test_obter_resumo_fundo_com_retorno_negativo():
        fundos = {"DELTA-08": _fundo("DELTA-08", -1.85, 3.05, [0.0, -0.9, -1.85])}
        out = agent._tool_obter_resumo(fundos, {"fundo": "DELTA-08"})
        assert out["resumo"]["retorno_cota"] < 0
    ```
  - `test_sinais.py` — testa `sinais.gerar_sinais` isoladamente com fixtures
    `FUNDO`/`AGG`/`NOTICIAS` em dict — copie o formato pra montar `noticias`
    de teste no plano abaixo.
  - **Não existe hoje** nenhum teste HTTP pra `/analisar`
    (`grep -rln '"/analisar"' services/prisma-api/tests/*.py` não retorna
    nada) — é um gap que este plano fecha.

## Comandos que você vai precisar

| Propósito | Comando | Esperado no sucesso |
|---|---|---|
| Testes backend (só os arquivos tocados) | `cd services/prisma-api && source ../../.venv/bin/activate && python -m pytest tests/test_agent_tools.py tests/test_agent_comparar_periodos.py tests/test_agent_db_integration.py tests/test_sinais.py tests/test_analisar_endpoint.py tests/test_busca_semantica_fundo.py -q` | todos passam |
| Testes backend completos | `cd services/prisma-api && source ../../.venv/bin/activate && python -m pytest -q` | todos passam (baseline atual: 195 passed, 5 skipped — confirme que não regrediu) |
| Postgres de dev (se ainda não estiver rodando) | `docker ps --format "{{.Names}}" \| grep prisma-db \|\| (cd /Users/fabiofigueiredo/Projetos/prisma && docker compose -f docker-compose.dev.yml up -d)` | container `prisma-db-1` `Up` |
| Banco de teste — recriar do zero (só se os testes falharem por coluna ausente) | `PGPASSWORD=prisma_dev psql -h 127.0.0.1 -p 55432 -U prisma -d prisma -c "DROP DATABASE IF EXISTS prisma_test; CREATE DATABASE prisma_test;"` | `DROP DATABASE` / `CREATE DATABASE` |
| Typecheck frontend | `cd apps/web && npx tsc --noEmit` | exit 0, sem erros |
| Lint frontend (arquivos tocados) | `cd apps/web && npx eslint src/app/\(app\)/copiloto/page.tsx src/app/\(app\)/sinais/page.tsx src/lib/api.ts` | exit 0 |

Esses comandos já foram usados e confirmados nesta sessão (não são
suposição). O `.venv` fica em `/Users/fabiofigueiredo/Projetos/prisma/.venv`
— ative-o antes de rodar pytest, senão faltam pacotes (`pyotp` etc.).

## Escopo

**Dentro do escopo** (únicos arquivos a modificar):
- `services/prisma-api/agent.py`
- `services/prisma-api/app.py` (só o bloco da rota `/analisar` e a
  atualização da chamada pra `agente.analisar`/`analisar_mock`)
- `services/prisma-api/tests/test_analisar_endpoint.py` (criar)
- `services/prisma-api/tests/test_agent_sinais_mercado.py` (criar)
- `apps/web/src/app/(app)/copiloto/page.tsx`
- `apps/web/src/lib/api.ts` (só se precisar ajustar o tipo — hoje já declara
  `degradado?: boolean`, provavelmente não precisa mexer)

**Fora do escopo** (não toque, mesmo que pareça relacionado):
- `services/prisma-api/sinais.py` e `services/prisma-api/radar.py` — já
  funcionam e já são testados; este plano só CONECTA o que existe, não
  reimplementa.
- `apps/web/src/app/(app)/sinais/page.tsx` e `radar/page.tsx` — telas
  próprias, fora do escopo (a menos que o passo 5 abaixo precise de um token
  de cor novo — se precisar, adicione o token, não mexa nessas páginas).
- Qualquer coisa em `app.py`, `auth.py`, `db/models.py` relacionada a
  autenticação/2FA/cadastro — pertence a outra frente de trabalho, já em
  andamento na árvore de trabalho (ver aviso no topo deste arquivo). Não
  toque nesses trechos mesmo que os veja modificados ao seu redor.
- O guardrail de escopo (`pede_recomendacao`) e o guardrail de injeção
  (`tenta_injecao`) em `app.py` — não mude o comportamento deles; o plano
  só adiciona um teste de regressão confirmando que continuam recusando.
- `docs/GOVERNANCA_IA.md`, `docs/SEGURANCA.md`, `docs/INTEGRATION_RISKS.md`
  — não precisam de edição; o código deve ficar consistente com o que já
  está documentado ali, não o contrário.

## Git workflow

- Branch: `advisor/002-copiloto-sinais-mercado` (repo não tem convenção de
  branch de feature documentada além de `feature/<nome>` observado em
  `git log` recente — use esse padrão se preferir).
- Commit por passo lógico; estilo de mensagem = Conventional Commits, como
  em `git log --oneline -10` (ex.: `feat(copiloto): tool de sinais de
  mercado no agente`, `fix(copiloto): expõe modo degradado no frontend`).
- NÃO dê push nem abra PR a menos que o operador tenha instruído.

## Passos

### Passo 1 — Nova tool `obter_sinais_mercado` no agente (P0)

Em `services/prisma-api/agent.py`:

1. Adicione ao topo do arquivo (junto dos outros imports de módulo local,
   sem criar import circular — `sinais.py` e `radar.py` não importam
   `agent.py`, então isso é seguro):
   ```python
   from sinais import gerar_sinais, AVISO_LEGAL as SINAIS_AVISO_LEGAL
   from radar import agregar as agregar_noticias
   ```
2. Adicione uma 6ª entrada em `TOOLS` (mesmo formato das 5 existentes),
   descrevendo quando usar (perguntas sobre "indicação de mercado",
   "sinal", "notícia", "probabilidade de risco" pra uma estratégia/fundo):
   ```python
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
   ```
3. Adicione a função de tool (perto de `_tool_obter_resumo`, mesmo estilo):
   ```python
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
   ```
   Note a assinatura com `noticias` explícito — **não** leia de um global;
   isso é threaded pelo chamador (passo 2).
4. Em `_tool_dispatch`, mude a assinatura pra receber `noticias` e adicione
   o novo ramo:
   ```python
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
   ```
5. Em `analisar(...)`, adicione o parâmetro `noticias: list[dict]` à
   assinatura (`def analisar(*, pergunta, fundo_ativo, backend, fundos,
   noticias, max_turns=4)`) e passe-o na chamada a `_tool_dispatch` (linha
   com `out = _tool_dispatch(tc["name"], tc["arguments"], fundos)` vira
   `out = _tool_dispatch(tc["name"], tc["arguments"], fundos, noticias)`).
6. Em `_bloco_grafico`, adicione um ramo pra `obter_sinais_mercado` — não
   precisa de gráfico novo (não há chart type de sinal na Meta atual),
   devolva `None` explicitamente pra ficar claro que é intencional (a
   função já devolve `None` no fallback, mas deixe o `if` explícito por
   clareza de manutenção):
   ```python
   if nome_tool == "obter_sinais_mercado":
       return None  # sinal é texto narrado, sem bloco de gráfico dedicado (Meta atual)
   ```
7. Atualize `SISTEMA_AGENTE` (o parágrafo de instrução) adicionando uma
   frase sobre a tool nova, no mesmo estilo das outras: depois de "Se a
   pergunta for sobre mudança/evolução entre períodos [...], use
   comparar_periodos.", adicione: "Se a pergunta for sobre indicação,
   sinal ou notícia de mercado para o fundo/estratégia, use
   obter_sinais_mercado — nunca infira sinal de mercado sem chamar essa
   ferramenta, e sempre inclua o aviso legal retornado por ela na resposta."

**Verificar**: `cd services/prisma-api && source ../../.venv/bin/activate && python -c "import agent; print(len(agent.TOOLS)); print([t['function']['name'] for t in agent.TOOLS])"` → imprime `6` e a lista com `obter_sinais_mercado` no final.

### Passo 2 — `analisar_mock` deixa de ser cego à pergunta (P0)

Ainda em `agent.py`, reescreva `analisar_mock` pra decidir a tool com base
em palavras-chave da pergunta, ANTES de decidir o fundo (mesmo espírito
determinístico do resto do arquivo — sem LLM, sem ambiguidade):

```python
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
```

Note que a assinatura ganhou `noticias: list[dict] | None = None` — mantenha
compatível com quem já chama sem esse argumento (nenhum teste existente
deveria quebrar, mas confira no passo de verificação).

**Verificar**: `python -c "
import agent
fundos = {'ALFA-33': {'fundo': {'nome': 'Alfa', 'codigo': 'ALFA-33', 'benchmark': 'CDI', 'periodo': '2T26', 'classe': 'X'}, 'resumo': {'retorno_cota': 1.0, 'retorno_bench': 0.5, 'excesso_pp': 0.5, 'pct_cdi': 200.0, 'beta': 0.5, 'alpha_pp': 0.5, 'vol_anual': 1.0, 'patrimonio_mm': 1.0, 'num_cotistas': 1}, 'estrategias': [{'nome': 'Caixa e Over', 'contribuicao_pp': 1.0, 'peso_medio': 100.0, 'cor': 'neutral'}], 'serie_diaria': [], 'ativos': [], 'fics': []}}
a = agent.analisar_mock(fundo_ativo='ALFA-33', fundos=fundos, noticias=[], pergunta='qual foi a rentabilidade?')
b = agent.analisar_mock(fundo_ativo='ALFA-33', fundos=fundos, noticias=[], pergunta='qual a indicação de mercado para esse fundo?')
assert a['resposta'] != b['resposta'], 'respostas iguais — bug NAO corrigido'
print('OK: respostas diferentes')
print(a['resposta'][:60])
print(b['resposta'][:60])
"` → imprime `OK: respostas diferentes` e duas frases visivelmente distintas.

### Passo 3 — Rota `/analisar` passa `noticias` e persiste `degradado` na auditoria (P0)

Em `services/prisma-api/app.py`, no handler de `/analisar`:

1. Onde hoje é `fundos = STATE.get("fundos") or {}`, adicione logo abaixo:
   `noticias = STATE.get("noticias") or []`.
2. Nas DUAS chamadas a `agente.analisar_mock(...)` (ramo `else` e ramo
   `except`), adicione `noticias=noticias` aos argumentos.
3. Na chamada a `agente.analisar(...)`, adicione `noticias=noticias` aos
   argumentos.
4. No `audit.registrar(...)` da mesma rota, adicione `degradado` dentro do
   dict `extra`:
   ```python
   audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                   backend=req.backend, latency_ms=lat,
                   fontes=[t["tool"] for t in resultado.get("tool_trace", [])],
                   bloqueados=[], resposta=resultado["resposta"],
                   extra={"consulta_echo": resultado.get("consulta_echo"),
                          "tool_trace": resultado.get("tool_trace"),
                          "degradado": degradado})
   ```

**Verificar**: `grep -n '"degradado": degradado' app.py` → aparece dentro do
bloco de `audit.registrar` da rota `/analisar` (não só no `return` final,
que já tinha antes).

### Passo 4 — Botão de ação "Sinais de Mercado" (P1)

Em `_gerar_acoes` (`agent.py`), adicione um 5º item, mesmo formato dos
outros:
```python
def _gerar_acoes(consulta_echo: dict) -> list[dict]:
    fundo = consulta_echo.get("fundo") or ""
    return [
        {"label": "Comparar Benchmarks", "prompt": f"Compare o {fundo} com o Ibovespa e o IMA-B"},
        {"label": "Ver por Grupo Contábil", "prompt": f"Mostre a atribuição do {fundo} por grupo contábil"},
        {"label": "Evolução no período", "prompt": f"Mostre o gráfico de evolução do {fundo} no período"},
        {"label": "Sinais de Mercado", "prompt": f"Qual a indicação de mercado para o {fundo}?"},
        {"label": "Exportar Relatório", "prompt": "__exportar_pdf__"},
    ]
```

**Verificar**: `python -c "import agent; a = agent._gerar_acoes({'fundo': 'X'}); assert any(x['label']=='Sinais de Mercado' for x in a); print('OK')"` → `OK`.

### Passo 5 — Frontend mostra quando a resposta está em modo degradado (P0)

Em `apps/web/src/app/(app)/copiloto/page.tsx`:

1. Logo após `const bloqueado = data.bloqueados.length > 0;` (linha 327),
   adicione: `const degradado = data.degradado === true;`
2. No bloco condicional (linhas ~406-432), adicione um terceiro ramo ANTES
   do `bloqueado`, pra degradado ter prioridade de exibição sobre o banner
   de sucesso genérico (mas depois do `data.escopo`, que já tem seu próprio
   tratamento e prioridade):
   ```tsx
   {data.escopo ? (
     ... // inalterado
   ) : degradado ? (
     <div className="flex items-center gap-2 rounded-lg border border-[var(--chart-5)]/40 bg-[var(--chart-5)]/10 px-3 py-1.5 text-xs text-[var(--chart-5)]">
       <ShieldAlert className="h-4 w-4" strokeWidth={1.75} />
       Modo demonstração — motor de IA real indisponível nesta consulta. Resposta gerada por regra fixa, não é análise fundamentada; não use para decisão.
     </div>
   ) : (
     <div className={cn(...)}>  {/* bloco bloqueado/sucesso, inalterado */}
       ...
     </div>
   )}
   ```
   Use o ícone `ShieldAlert` (já importado no arquivo, usado no ramo
   `bloqueado`) e o token `--chart-5` (mesmo tom âmbar do banner de "fora de
   escopo" logo acima, já que é aviso, não erro nem sucesso).

**Verificar**: `cd apps/web && npx tsc --noEmit` → exit 0. Depois, manual:
suba a API sem `GROQ_API_KEY` no ambiente
(`cd services/prisma-api && source ../../.venv/bin/activate && PRISMA_JWT_SECRET=dev unset GROQ_API_KEY; python -m uvicorn app:app --port 8000`)
e o frontend (`cd apps/web && npx next dev -p 3100`), abra
`/copiloto`, selecione motor "Nuvem", pergunte algo — o banner âmbar de modo
demonstração deve aparecer em vez do banner verde de sucesso.

## Plano de testes

Backend, dois arquivos novos:

- `services/prisma-api/tests/test_agent_sinais_mercado.py` — modelado em
  `tests/test_agent_tools.py` (fixture `_fundo` igual, sem HTTP). Casos:
  - `test_obter_sinais_mercado_devolve_sinal_ordenado_por_risco` — usa
    fixtures de notícia no formato de `tests/test_sinais.py`
    (`{"id": "n07", "estrategia": "Bolsa Brasil"}`), confirma que
    `_tool_obter_sinais_mercado` devolve `sinais` não vazio com `nivel` e
    `evidencias` presentes, e que `aviso_legal` bate com
    `sinais.AVISO_LEGAL`.
  - `test_obter_sinais_mercado_sem_noticias_nao_inventa` — `noticias=[]` →
    `sinais: []` e `aviso` presente explicando a ausência (nunca inventar
    sinal sem dado, mesmo princípio de `_tool_obter_atribuicao`).
  - `test_obter_sinais_mercado_fundo_inexistente_retorna_erro`.
  - `test_analisar_mock_pergunta_sobre_rentabilidade_difere_de_pergunta_sobre_mercado`
    — o teste do Passo 2 acima, formalizado (é a regressão do bug
    original — não pode voltar a ser removido/quebrado).
  - `test_analisar_mock_pergunta_evolucao_devolve_grafico_linha_nao_waterfall`
    — confirma `blocos[0]["chart"] == "linha"` (hoje devolveria
    `"waterfall"`, incorretamente, pro mesmo prompt do botão "Evolução no
    período").
  - `test_analisar_mock_pergunta_grupo_contabil_muda_dimensao` — só roda se
    houver dado de grupo contábil no Postgres de teste (siga o padrão de
    `tests/test_agent_db_integration.py::test_dimensao_grupo_contabil_busca_no_postgres_quando_disponivel`
    pra fixture); se não houver, aceite o aviso de fallback como já
    coberto por aquele teste existente — não duplique.

- `services/prisma-api/tests/test_analisar_endpoint.py` — NOVO, primeiro
  teste HTTP da rota `/analisar` (gap de cobertura confirmado nesta
  auditoria). Modele o `TestClient`/fixture de `db` conforme
  `tests/test_cadastro_convite.py` (engine `prisma_test`,
  `Base.metadata.create_all`, savepoint por teste) — mas note que
  `/analisar` não depende de `db` diretamente, então pode ser mais simples;
  veja `tests/test_bloqueio_e_rate_limit.py` pro padrão de `test_app`
  fixture com `TestClient(app_module.app)` sem overrides de banco se
  `/analisar` não usar `Depends(get_db)`. Casos:
  - `test_analisar_pergunta_rentabilidade_backend_mock` — `backend="mock"`,
    `pergunta="Qual foi a rentabilidade do fundo no semestre?"` → 200,
    `degradado is True` (mock é sempre degradado por definição), resposta
    contém `"(Demonstração)"`.
  - `test_analisar_pergunta_mercado_backend_mock_difere_da_de_rentabilidade`
    — mesmo fundo, pergunta muda pra "qual a indicação de mercado", resposta
    HTTP diferente da anterior (regressão end-to-end do bug original, não só
    no nível de função).
  - `test_analisar_pede_recomendacao_e_recusado` — pergunta
    `"Devo comprar mais cotas desse fundo?"` → resposta é a
    `RESPOSTA_ESCOPO` fixa, `escopo: True`, **NÃO** chama nenhuma tool —
    este é o teste de regressão do guardrail de `docs/GOVERNANCA_IA.md` §1;
    NÃO pode passar a responder normalmente depois deste plano.
  - `test_analisar_tentativa_injecao_e_bloqueada` — mesmo padrão pro
    guardrail de injeção (`tenta_injecao`), pra não regredir.
  - `test_analisar_audit_registra_degradado` — depois de uma chamada com
    `backend="mock"`, confirme (via o mesmo mecanismo que
    `tests/test_audit_postgres.py` ou `tests/test_audit.py` usam pra ler
    eventos gravados) que o evento de auditoria da rota `/analisar` tem
    `extra["degradado"] is True`. Leia esses dois arquivos primeiro pra
    saber qual storage de auditoria está ativo no ambiente de teste
    (arquivo vs Postgres) e siga o mesmo padrão de asserção.

Frontend: nenhum teste novo obrigatório neste plano (a mudança é só
condicional de renderização); se o repo tiver um padrão de teste de
componente pro `copiloto` (`apps/web/src/app/(app)/copiloto/__tests__/`),
confira se `BlocoView.test.tsx` cobre o banner e, se for barato, adicione um
caso `degradado=true` seguindo o mesmo padrão — não é bloqueante pro `done`
deste plano se o esforço for desproporcional.

Verificação final: `cd services/prisma-api && source ../../.venv/bin/activate && python -m pytest -q` → todos passam, incluindo os novos.

## Critérios de conclusão

Verificáveis por máquina. TODOS precisam valer:

- [ ] `python -c "import agent; assert len(agent.TOOLS) == 6"` não levanta erro
- [ ] `python -m pytest services/prisma-api/tests/test_agent_sinais_mercado.py services/prisma-api/tests/test_analisar_endpoint.py -q` → todos passam
- [ ] `python -m pytest services/prisma-api -q` → todos passam (nenhuma regressão na suíte completa, baseline 195 passed/5 skipped antes deste plano)
- [ ] `cd apps/web && npx tsc --noEmit` → exit 0
- [ ] `grep -n "degradado" apps/web/src/app/\(app\)/copiloto/page.tsx` → tem match (hoje não tem nenhum)
- [ ] `grep -n '"degradado": degradado' services/prisma-api/app.py` → aparece dentro do `audit.registrar` de `/analisar`, não só no `return`
- [ ] Nenhum arquivo fora da lista de "Dentro do escopo" foi modificado (`git status`)
- [ ] `plans/README.md` — linha de status do plano 002 atualizada

## STOP conditions

Pare e reporte (não improvise) se:

- O código em `services/prisma-api/agent.py` já tiver uma tool chamada
  `obter_sinais_mercado` ou algo equivalente (`sinais`/`radar` já wired) —
  significa que alguém já resolveu isso; compare com o que está aqui e não
  duplique.
- `grep -rln '"/analisar"' services/prisma-api/tests/*.py` já retornar
  arquivos — o gap de cobertura pode já ter sido fechado por outro plano;
  leia o que existe antes de criar `test_analisar_endpoint.py` do zero.
- O `TestClient` de `/analisar` exigir um `Depends(get_db)` que hoje não
  existe (drift na assinatura da rota) — pare, isso muda a estratégia de
  fixture do teste HTTP.
- Descobrir que `audit.registrar`/o mecanismo de leitura de auditoria mudou
  de forma incompatível com `extra={...}` como dict simples — pare e
  reporte em vez de adaptar às cegas (auditoria em ambiente regulado não é
  lugar pra gambiarra).
- Qualquer teste de regressão do guardrail de escopo/injeção
  (`test_analisar_pede_recomendacao_e_recusado`,
  `test_analisar_tentativa_injecao_e_bloqueada`) falhar depois das suas
  mudanças — significa que você tocou em algo que não devia; reverta o
  passo mais recente antes de continuar.

## Notas de manutenção

- Se um dia `sinais.py` ganhar uma v1 com backtest real (mencionado em
  `docs/GOVERNANCA_IA.md` §3 como "estado de validação: v0 sem backtest;
  v1 (piloto) com hit-rate publicado"), o texto gerado em `analisar_mock`
  e o `SISTEMA_AGENTE` devem passar a mencionar o hit-rate — sinalize isso
  como follow-up quando a v1 chegar, não é escopo deste plano.
- Se o motor real (`analisar`, LLM com tool-calling) começar a ser usado de
  verdade em produção (com `GROQ_API_KEY` configurada), teste manualmente
  se o LLM realmente chama `obter_sinais_mercado` quando apropriado — o
  `SISTEMA_AGENTE` foi atualizado por instrução em prompt, que é
  probabilístico por natureza; o teste automatizado deste plano só cobre o
  caminho determinístico (`analisar_mock`). Considere um teste de fumaça
  periódico contra o backend real, fora do escopo deste plano.
- O revisor deve prestar atenção especial ao Passo 2: é a mudança de maior
  superfície (reescreve `analisar_mock` inteira). Confirme que o
  comportamento pra perguntas SEM palavra-chave de sinal/evolução/grupo
  contábil continua idêntico ao anterior (mesma resposta de atribuição por
  estratégia) — a reescrita deve ser estritamente aditiva em capacidade, não
  mudar o caminho feliz existente.
- Item pendente já identificado mas **explicitamente fora deste plano**: a
  suspeita de contaminação de senha entre usuários e lacunas de UX em "Meu
  Perfil"/atribuição de papel, do mesmo teste manual — ver
  `plans/003-verificar-isolamento-senha-usuarios.md`.
