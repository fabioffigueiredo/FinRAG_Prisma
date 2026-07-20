# Plan 006: `analisar_mock` avisa quando a pergunta cita um código de fundo que não existe

> **Executor instructions**: Siga este plano passo a passo. Rode cada comando
> de verificação e confirme o resultado esperado antes do próximo passo. Se
> algo na seção "STOP conditions" ocorrer, pare e reporte — não improvise.
> Ao terminar, atualize a linha de status deste plano em `plans/README.md`
> (a menos que quem te despachou tenha dito que cuida do índice).
>
> **Drift check (rode primeiro)**: `git diff --stat d0cb607..HEAD -- services/prisma-api/agent.py`
> Compare o trecho de "Estado atual" abaixo com o código ao vivo antes de
> prosseguir; em caso de divergência, trate como condição de STOP.

## Status

- **Priority**: P2 (trust/UX — não é alucinação de número, é substituição
  silenciosa de contexto; menor severidade que os achados P0 já corrigidos
  nos planos 002/005)
- **Effort**: S
- **Risk**: LOW (aditivo — só adiciona um ramo de "não encontrado" antes do
  fallback existente; não muda nenhum caminho que já funciona)
- **Depends on**: none
- **Category**: bug (UX de confiança/transparência)
- **Planned at**: commit `081ff8f`, 2026-07-20

## Por que isso importa

Ao executar `plans/004-catalogo-cenarios-gestor-copiloto.md` (Categoria D,
"fundo inexistente"), o teste
`test_fundo_inexistente_devolve_mensagem_compreensivel_nao_traceback` falhou
— não com um traceback (o que seria pior), mas porque `analisar_mock`
responde com dados de OUTRO fundo, sem avisar, quando a pergunta cita um
código que não existe:

```
pergunta: "mostra o fundo XYZ-99"
fundo em foco na tela: ALFA-33
resposta obtida: "(Demonstração) O Fundo ALFA-33 teve retorno de 1.00% no
                  período, ante 0.50% do CDI — excesso de +0.50 pp. ..."
```

Confirmado nesta sessão (revisão do plano 004, não é conclusão do
executor): a causa é que `_detectar_fundo_citado` (agent.py) só reconhece um
fundo citado se o código/alias JÁ EXISTIR no dict `fundos` — quando não
bate com nada conhecido, a função devolve `None` silenciosamente, e
`analisar_mock` cai de volta pro `fundo_ativo` (o fundo que estava em foco
na tela) sem qualquer indicação de que o fundo pedido não foi encontrado.

Isso não é alucinação de número (o sistema não inventa dados pra XYZ-99 —
ele responde corretamente sobre ALFA-33), mas é uma falha de confiança
concreta: um gestor que digita um código errado, ou pergunta sobre um fundo
que não pertence à gestora, recebe uma resposta CONFIANTE e bem formatada
sobre um fundo diferente do que pediu, sem perceber a troca. No mesmo
espírito do resto do trabalho desta sessão (tornar o modo degradado visível
em vez de silencioso, plano 002) — esse é outro caso de "o sistema faz algo
diferente do pedido sem avisar."

## Estado atual

`services/prisma-api/agent.py`, função `_detectar_fundo_citado` (linhas
213-229):

```python
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
```

Início de `analisar_mock` (depois do plano 002; linhas ~426-430):

```python
def analisar_mock(*, fundo_ativo: str, fundos: dict, noticias: list[dict] | None = None, pergunta: str = "") -> dict:
    """..."""
    noticias = noticias or []
    fundo_citado = _detectar_fundo_citado(pergunta, fundos)
    fundo_alvo = fundo_citado or fundo_ativo
    pergunta_low = (pergunta or "").lower()
    ...
```

Os fundos do seed seguem o padrão `LETRAS-NÚMERO` (`ALFA-33`, `BETA-71`,
`DELTA-08`, `GAMA-12` — confirme os códigos reais do seed ao rodar
`python -c "import app; print(list(app.STATE.get('fundos', {}).keys()))"`
dentro do contexto de teste, ou inspecione o arquivo de seed usado pelos
testes existentes).

Teste já escrito (não commitado ainda nesta worktree, criado pela execução
anterior do plano 004 — `services/prisma-api/tests/test_copiloto_cenarios_gestor.py`):

```python
def test_fundo_inexistente_devolve_mensagem_compreensivel_nao_traceback():
    fundos = {"ALFA-33": _fundo("ALFA-33")}
    out = agent.analisar_mock(fundo_ativo="ALFA-33", fundos=fundos, noticias=[],
                              pergunta="mostra o fundo XYZ-99")
    assert "não encontrado" in out["resposta"] or "erro" in out["resposta"].lower()
```

Este teste já existe e não deve ser modificado por este plano — ele é o
critério de aceite.

## Comandos que você vai precisar

| Propósito | Comando | Esperado no sucesso |
|---|---|---|
| Teste do achado | `cd services/prisma-api && source .venv/bin/activate && python -m pytest tests/test_copiloto_cenarios_gestor.py -v` | todos passam (8/8 nesta worktree, já que a Categoria E foi corrigida pelo plano 005) |
| Testes de agent.py | `cd services/prisma-api && source .venv/bin/activate && python -m pytest tests/test_agent_tools.py tests/test_agent_sinais_mercado.py tests/test_busca_semantica_fundo.py -q` | todos passam, sem regressão em detecção de fundo por nome/alias |
| Suíte completa | `cd services/prisma-api && source .venv/bin/activate && python -m pytest -q` | todos passam, sem regressão |

## Escopo

**Dentro do escopo**:
- `services/prisma-api/agent.py` (só a área de `_detectar_fundo_citado`/
  `analisar_mock`)
- `services/prisma-api/tests/test_agent_tools.py` OU um novo arquivo de
  teste dedicado, se preferir (ver Passo 2) — para testar a nova função
  auxiliar isoladamente

**Fora do escopo**:
- `services/prisma-api/tests/test_copiloto_cenarios_gestor.py` — já existe
  (do plano 004) e não deve ser editado; ele é o critério de aceite, não
  algo a ajustar.
- O caminho real com LLM (`analisar`, tool-calling) — ele já tem
  `resolver_fundo` como tool disponível, que devolve `{"erro": "..."}"`
  quando não encontra; a decisão de chamar essa tool antes de responder é
  do LLM, guiada por `SISTEMA_AGENTE`, e está fora do escopo determinístico
  deste plano (não dá pra "consertar" um comportamento probabilístico com
  uma regra fixa).
- `_ALIASES_FUNDO`, `construir_indice_semantico_fundos` — não mude a lógica
  de resolução por alias/nome/semântica, só adicione a checagem de "parece
  código de fundo mas não existe" como um caso NOVO, adicional.

## Git workflow

- Branch: `advisor/006-avisar-fundo-nao-reconhecido`.
- Um commit; Conventional Commits (ex.: `fix(copiloto): avisa quando pergunta
  cita fundo inexistente em vez de responder sobre outro`).
- NÃO dê push nem abra PR a menos que instruído.

## Passos

### Passo 1 — Detectar menção a um código de fundo que não existe

Em `services/prisma-api/agent.py`, adicione logo após `_detectar_fundo_citado`:

```python
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
```

**Verificar**: `python -c "
import agent
fundos = {'ALFA-33': {}}
assert agent._fundo_nao_reconhecido_citado('mostra o fundo XYZ-99', fundos) == 'XYZ-99'
assert agent._fundo_nao_reconhecido_citado('mostra o fundo ALFA-33', fundos) is None
assert agent._fundo_nao_reconhecido_citado('qual foi a rentabilidade?', fundos) is None
print('OK')
"` → imprime `OK`.

### Passo 2 — Usar a checagem em `analisar_mock` antes do fallback pro fundo em foco

Em `analisar_mock`, logo após calcular `fundo_citado`, adicione a checagem
ANTES de montar `fundo_alvo`:

```python
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
```

Note a ordem: `_detectar_fundo_citado` roda PRIMEIRO — se a pergunta citar
um fundo que EXISTE, o comportamento não muda em nada. A checagem nova só
entra quando NENHUM fundo conhecido foi citado E a pergunta parece
mencionar um código que não existe.

**Verificar**: `python -c "
import agent
fundos = {'ALFA-33': {'fundo': {'nome': 'Fundo ALFA-33', 'codigo': 'ALFA-33', 'benchmark': 'CDI', 'periodo': '2T26', 'classe': 'X'}, 'resumo': {'retorno_cota': 1.0, 'retorno_bench': 0.5, 'excesso_pp': 0.5, 'pct_cdi': 200.0, 'beta': 0.5, 'alpha_pp': 0.5, 'vol_anual': 1.0, 'patrimonio_mm': 1.0, 'num_cotistas': 1}, 'estrategias': [{'nome': 'Caixa e Over', 'contribuicao_pp': 1.0, 'peso_medio': 100.0, 'cor': 'neutral'}], 'serie_diaria': [], 'ativos': [], 'fics': []}}
out = agent.analisar_mock(fundo_ativo='ALFA-33', fundos=fundos, noticias=[], pergunta='mostra o fundo XYZ-99')
assert 'não encontrado' in out['resposta'], out['resposta']
assert 'ALFA' not in out['resposta']
print('OK:', out['resposta'])
"` → imprime `OK: (Demonstração) Fundo 'XYZ-99' não encontrado — verifique o código e tente novamente.`

### Passo 3 — Confirmar que perguntas normais (sem código inexistente) continuam idênticas

```python
python -c "
import agent
fundos = {'ALFA-33': {'fundo': {'nome': 'Fundo ALFA-33', 'codigo': 'ALFA-33', 'benchmark': 'CDI', 'periodo': '2T26', 'classe': 'X'}, 'resumo': {'retorno_cota': 1.0, 'retorno_bench': 0.5, 'excesso_pp': 0.5, 'pct_cdi': 200.0, 'beta': 0.5, 'alpha_pp': 0.5, 'vol_anual': 1.0, 'patrimonio_mm': 1.0, 'num_cotistas': 1}, 'estrategias': [{'nome': 'Caixa e Over', 'contribuicao_pp': 1.0, 'peso_medio': 100.0, 'cor': 'neutral'}], 'serie_diaria': [], 'ativos': [], 'fics': []}}
out = agent.analisar_mock(fundo_ativo='ALFA-33', fundos=fundos, noticias=[], pergunta='qual foi a rentabilidade do fundo no semestre?')
assert 'não encontrado' not in out['resposta']
assert 'ALFA-33' in out['resposta']
print('OK: pergunta normal continua respondendo sobre o fundo em foco')
"
```

**Verificar**: imprime `OK`, sem `AssertionError`.

### Passo 4 — Rodar o teste do plano 004 (critério de aceite)

```
cd services/prisma-api && source .venv/bin/activate && python -m pytest tests/test_copiloto_cenarios_gestor.py -v
```

**Verificar**: todos os 8 testes desse arquivo passam agora (Categoria D
que falhava antes deste plano, mais as 7 que já passavam desde o plano 005).

## Plano de testes

- `_fundo_nao_reconhecido_citado` — teste unitário direto (Passo 1),
  formalize em `tests/test_agent_tools.py` (ou crie
  `tests/test_agent_deteccao_fundo.py` se preferir isolar): casos com
  código inexistente, código existente, e pergunta sem nenhum código.
- `analisar_mock` com fundo inexistente citado — formalize o Passo 2 como
  teste (`test_analisar_mock_fundo_citado_inexistente_avisa_sem_trocar_de_fundo`),
  além do teste já existente em `test_copiloto_cenarios_gestor.py` (que não
  deve ser editado, é o critério de aceite externo).
- Regressão: `analisar_mock` com pergunta sem nenhum código (Passo 3).

Verificação final: `cd services/prisma-api && source .venv/bin/activate && python -m pytest -q` → todos passam, incluindo os novos, sem regressão.

## Critérios de conclusão

- [ ] `python -m pytest tests/test_copiloto_cenarios_gestor.py -v` → todos os 8 testes passam
- [ ] `python -m pytest services/prisma-api -q` → sem regressão na suíte completa
- [ ] Pergunta sem código de fundo inexistente continua com resposta idêntica a antes deste plano (Passo 3)
- [ ] Pergunta citando um fundo REAL por código/alias/nome continua funcionando (não testar de novo do zero — rodar `test_busca_semantica_fundo.py` e os testes de `_detectar_fundo_citado` existentes já cobre isso)
- [ ] Nenhum arquivo fora do escopo foi modificado (`git status`), especialmente `test_copiloto_cenarios_gestor.py` intocado
- [ ] `plans/README.md` — SKIP se dispatchado via `execute`

## STOP conditions

Pare e reporte (não improvise) se:

- O regex `_PADRAO_CODIGO_FUNDO` capturar falsos positivos em perguntas
  legítimas durante os testes de regressão (ex.: alguma pergunta menciona
  algo tipo "2T-26" ou similar que não é código de fundo mas bate no
  padrão) — ajuste o regex uma vez pra ser mais específico (ex.: exigir que
  a parte de letras tenha pelo menos 3 caracteres, ou negative-lookahead
  pra padrões de período/data conhecidos); se não conseguir sem reintroduzir
  o problema original, pare e reporte o trade-off.
- Algum teste de detecção de fundo por NOME (não código) começar a falhar —
  a checagem nova deve rodar só quando `_detectar_fundo_citado` já
  devolveu `None` (nenhum fundo reconhecido por código/alias/nome), então
  não deveria interferir, mas confirme.
- O código dos fundos reais do seed não seguir o padrão `LETRAS-NÚMERO`
  assumido (`ALFA-33` etc.) — pare e reporte o padrão real observado antes
  de ajustar o regex.

## Notas de manutenção

- Esta é uma heurística determinística sobre formato de texto, não uma
  verificação semântica — ela não pega, por exemplo, "mostra o fundo Zeta"
  (nome sem código reconhecível de um fundo que não existe); isso já cai no
  comportamento anterior (fallback pro fundo em foco), que é aceitável
  nesse caso porque não HÁ um código explícito e inequívoco sendo ignorado.
- Se o padrão de código de fundos mudar no futuro (ex.: passar a incluir
  underscore, ou ter mais dígitos), `_PADRAO_CODIGO_FUNDO` precisa ser
  revisado junto.
