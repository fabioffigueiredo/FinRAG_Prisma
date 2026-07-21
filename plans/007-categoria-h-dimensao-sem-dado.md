# Plan 007: Fechar a Categoria H do catálogo de cenários (dimensão/período sem dado)

> **Executor instructions**: Siga este plano passo a passo. Rode cada comando
> de verificação e confirme o resultado esperado antes do próximo passo. Se
> algo na seção "STOP conditions" ocorrer, pare e reporte — não improvise.
> Ao terminar, atualize a linha de status deste plano em `plans/README.md`
> (a menos que quem te despachou tenha dito que cuida do índice).
>
> **Drift check (rode primeiro)**: `git diff --stat b368ef6..HEAD -- services/prisma-api/agent.py services/prisma-api/tests/test_agent_db_integration.py services/prisma-api/tests/test_copiloto_cenarios_gestor.py`
> Se algum desses arquivos mudou desde que este plano foi escrito, compare os
> trechos de "Estado atual" abaixo com o código ao vivo antes de prosseguir;
> em caso de divergência, trate como condição de STOP.

## Status

- **Priority**: P2 (cobertura de teste, não corrige bug de produção — os
  caminhos de fallback já existem e funcionam, só faltam os testes)
- **Effort**: S
- **Risk**: LOW (só testes novos; nenhuma mudança em código de produção)
- **Depends on**: none
- **Category**: tests
- **Planned at**: commit `b368ef6`, 2026-07-20

## Por que isso importa

`docs/superpowers/specs/2026-07-20-copiloto-cenarios-gestor-design.md`
definiu 10 categorias de cenário (A-J) pro catálogo de testes do copiloto.
`plans/004-catalogo-cenarios-gestor-copiloto.md` (já executado, revisado,
mergeado em main e deployado em produção) implementou 8 delas (A, B, C, D,
E, F, G, J) — mas nunca escreveu um Passo concreto pra **Categoria H**
("dimensão ou período sem dado disponível"), apesar de citá-la nos
"Critérios de conclusão" ("pelo menos 10 funções de teste... H pode ter
mais de uma"). Isso foi identificado e registrado como inconsistência não
bloqueante no relatório do executor do plano 004, e ficou pendente desde
então.

A categoria já tem cobertura PARCIAL em `test_agent_db_integration.py`
(dimensão `grupo_contabil`, quando o Postgres está/não está semeado com
esse dado) — o que falta é estender pras outras dimensões citadas na spec
original (`renda_variavel`, `privados`) e formalizar isso dentro do arquivo
de catálogo (`test_copiloto_cenarios_gestor.py`), pra fechar o gap de
autoria do plano 004 sem duplicar o que já existe.

## Estado atual

`services/prisma-api/agent.py`:
```python
DIMENSOES_VALIDAS = [
    "estrategia", "grupo_contabil", "supergrupo", "vencimento",
    "privados", "renda_variavel", "renda_fixa", "ativos",
]
```

`_tool_obter_atribuicao` (já existe, não muda neste plano) — quando a
dimensão pedida não é `"estrategia"` e não há dado no Postgres pra ela,
cai num aviso determinístico e volta pra `"estrategia"`:
```python
avisos = []
if dimensao != "estrategia":
    dados_db = _obter_contribuicoes_db(cod, periodo, dimensao)
    if dados_db:
        estrategias = dados_db
        ...
    else:
        avisos.append(
            f"Dimensão '{DIMENSOES_LABEL.get(dimensao, dimensao)}' ainda não está disponível "
            "na base de demonstração — mostrando por Estratégia (na integração real, essa "
            "dimensão vem diretamente da plataforma de atribuição)."
        )
        dimensao = "estrategia"
```

`services/prisma-api/tests/test_agent_db_integration.py` (íntegra, não
muda neste plano — só serve de exemplar e não deve ser duplicado):
```python
import agent

PERIODO_REAL = "2º trimestre 2026 (abr–jun)"


def _fundo_alfa_real():
    return {
        "ALFA-33": {
            "fundo": {"nome": "Alfa Multimercado FIC FIM", "codigo": "ALFA-33",
                     "benchmark": "CDI", "periodo": PERIODO_REAL, "classe": "Multimercado Macro"},
            "resumo": {"retorno_cota": 4.25, "retorno_bench": 3.10, "excesso_pp": 1.15,
                      "pct_cdi": 137.1, "beta": 0.15, "alpha_pp": 1.10, "vol_anual": 4.8,
                      "patrimonio_mm": 1284.6, "num_cotistas": 3120},
            "estrategias": [{"nome": "Crédito Privado", "contribuicao_pp": 1.35,
                            "peso_medio": 28.0, "cor": "gold"}],
            "serie_diaria": [], "ativos": [], "fics": [],
        }
    }


def test_dimensao_grupo_contabil_busca_no_postgres_quando_disponivel():
    fundos = _fundo_alfa_real()
    out = agent._tool_obter_atribuicao(fundos, {"fundo": "ALFA-33", "dimensao": "grupo_contabil"})
    if not out["estrategias"] or out["dimensao"] != "grupo_contabil":
        import pytest
        pytest.skip("Postgres de dev indisponível/não semeado — rode docker-compose.dev.yml + seed_db")
    assert out["dimensao"] == "grupo_contabil"
    assert out["aviso"] is None
    assert len(out["estrategias"]) >= 1
    assert all("nome" in e and "contribuicao_pp" in e for e in out["estrategias"])


def test_dimensao_sem_dado_no_banco_cai_no_aviso_antigo():
    fundos = _fundo_alfa_real()
    fundos["ALFA-33"]["fundo"]["periodo"] = "período que não existe no banco"
    out = agent._tool_obter_atribuicao(fundos, {"fundo": "ALFA-33", "dimensao": "grupo_contabil"})
    assert out["dimensao"] == "estrategia"
    assert out["aviso"] is not None
    assert "não está disponível" in out["aviso"]
```

O segundo teste (`test_dimensao_sem_dado_no_banco_cai_no_aviso_antigo`) é
determinístico e NÃO depende do Postgres estar de pé — ele força a
divergência mudando o período pra um que nunca existiria no banco. Esse é
o padrão a seguir pra `renda_variavel`/`privados`, evitando testes que
dependem de estado externo (Postgres semeado) além do que já é aceito no
primeiro teste (que já tem `pytest.skip` de guarda).

`services/prisma-api/tests/test_copiloto_cenarios_gestor.py` (já existe,
criado pelo plano 004 — íntegra completa relevante, note a estrutura por
blocos de categoria com comentário `# --- X. Nome ---`):
```python
"""Catálogo amplo de cenários de gestor de fundos para o copiloto
"Pergunte ao Prisma" — ver docs/superpowers/specs/2026-07-20-copiloto-cenarios-gestor-design.md
pro racional completo (pesquisa CVM/BACEN incluída). Cada bloco de teste
corresponde a uma categoria do catálogo.
"""
import agent
from fastapi.testclient import TestClient


def _fundo(codigo, retorno_cota=1.0, retorno_bench=0.5, benchmark="CDI"):
    return {
        "fundo": {"nome": f"Fundo {codigo}", "codigo": codigo, "benchmark": benchmark,
                  "periodo": "2T26", "classe": "Multimercado"},
        "resumo": {"retorno_cota": retorno_cota, "retorno_bench": retorno_bench,
                   "excesso_pp": round(retorno_cota - retorno_bench, 2), "pct_cdi": 0.0,
                   "beta": 0.5, "alpha_pp": round(retorno_cota - retorno_bench, 2),
                   "vol_anual": 1.0, "patrimonio_mm": 1.0, "num_cotistas": 1},
        "estrategias": [{"nome": "Caixa e Over", "contribuicao_pp": retorno_cota,
                        "peso_medio": 100.0, "cor": "neutral"}],
        "serie_diaria": [{"data": "2026-04-01", "cota": 0.0, "bench": 0.0}],
        "ativos": [], "fics": [],
    }

# ... blocos A a G já existem (rentabilidade, sinais, benchmark composto,
# fundo inexistente, recomendação, previsão, injeção) ...

# --- J. Caracterização: rotas de análise são públicas hoje (por design) ----

def test_analisar_responde_sem_sessao_hoje_caracterizacao():
    ...
```
(bloco J é o último do arquivo hoje — o novo bloco H entra ANTES dele,
mantendo a ordem alfabética das categorias já estabelecida no arquivo.)

## Comandos que você vai precisar

| Propósito | Comando | Esperado no sucesso |
|---|---|---|
| Postgres de dev (se não estiver rodando) | `docker ps --format "{{.Names}}" \| grep prisma-db` (reuse; não inicie um novo) | container `Up` |
| Teste do catálogo | `cd services/prisma-api && source ../../.venv/bin/activate && python -m pytest tests/test_copiloto_cenarios_gestor.py -v` | todos passam, incluindo os novos de Categoria H |
| Suíte completa | `cd services/prisma-api && source ../../.venv/bin/activate && python -m pytest -q` | todos passam, sem regressão (baseline atual: 226 passed, 6 skipped) |

## Escopo

**Dentro do escopo**:
- `services/prisma-api/tests/test_copiloto_cenarios_gestor.py` (adicionar
  o bloco da Categoria H, entre os blocos G e J)

**Fora do escopo**:
- Qualquer arquivo de produção (`agent.py`) — os caminhos de fallback já
  existem e funcionam; este plano só formaliza teste, não muda
  comportamento.
- `services/prisma-api/tests/test_agent_db_integration.py` — já cobre
  `grupo_contabil`; não duplique esses casos, só estenda pras dimensões
  que faltam, no arquivo do catálogo.
- As outras categorias (A-G, J) do arquivo — não toque nelas.

## Git workflow

- Branch: `advisor/007-categoria-h-dimensao-sem-dado`.
- Um commit; Conventional Commits (ex.: `test(copiloto): fecha Categoria H
  do catálogo — dimensão sem dado disponível`).
- NÃO dê push nem abra PR a menos que instruído.

## Passos

### Passo 1 — Adicionar o bloco da Categoria H

Em `services/prisma-api/tests/test_copiloto_cenarios_gestor.py`, insira o
bloco abaixo IMEDIATAMENTE ANTES do comentário `# --- J. Caracterização...`
(mantendo a ordem alfabética das categorias já estabelecida no arquivo):

```python
# --- H. Dimensão ou período sem dado disponível -----------------------------

def test_dimensao_renda_variavel_sem_dado_cai_no_aviso_de_estrategia():
    """Mesmo padrão determinístico de
    test_agent_db_integration.py::test_dimensao_sem_dado_no_banco_cai_no_aviso_antigo
    — força a divergência via período inexistente, não depende do Postgres
    estar semeado."""
    fundo = _fundo("ALFA-33")
    fundo["fundo"]["periodo"] = "período que não existe no banco"
    fundos = {"ALFA-33": fundo}
    out = agent._tool_obter_atribuicao(fundos, {"fundo": "ALFA-33", "dimensao": "renda_variavel"})
    assert out["dimensao"] == "estrategia"
    assert out["aviso"] is not None
    assert "não está disponível" in out["aviso"]


def test_dimensao_privados_sem_dado_cai_no_aviso_de_estrategia():
    fundo = _fundo("ALFA-33")
    fundo["fundo"]["periodo"] = "período que não existe no banco"
    fundos = {"ALFA-33": fundo}
    out = agent._tool_obter_atribuicao(fundos, {"fundo": "ALFA-33", "dimensao": "privados"})
    assert out["dimensao"] == "estrategia"
    assert out["aviso"] is not None
    assert "não está disponível" in out["aviso"]


def test_pergunta_periodo_fora_do_disponivel_avisa_em_vez_de_inventar():
    """Categoria H também cobre período fora do único disponível no seed
    (não só dimensão) — via analisar_mock, pergunta em linguagem natural."""
    fundos = {"ALFA-33": _fundo("ALFA-33")}
    out = agent.analisar_mock(fundo_ativo="ALFA-33", fundos=fundos, noticias=[],
                              pergunta="como foi a rentabilidade do fundo no ano passado?")
    # não deve levantar exceção nem inventar um período diferente do
    # configurado no fundo — a resposta narra o período real disponível
    assert "erro" not in out or "resposta" in out
    assert out["resposta"]
```

O terceiro teste (`test_pergunta_periodo_fora_do_disponivel_avisa_em_vez_de_inventar`)
é deliberadamente permissivo na asserção — o ponto central da Categoria H
pra período (diferente de dimensão) é que o sistema NUNCA finge ter dado de
um período diferente do que existe no seed (comportamento já garantido por
`_resolver_periodo`, que só sinaliza divergência, nunca troca o dado
retornado). Se esse teste revelar que o sistema efetivamente troca de
período ou inventa números pra um período inexistente, isso é STOP (ver
abaixo), não um ajuste de asserção.

**Verificar**: `python -m pytest tests/test_copiloto_cenarios_gestor.py -v` → todos os 11 testes do arquivo passam (8 anteriores + 3 novos).

## Plano de testes

Já é o conteúdo do Passo 1 — 3 funções novas, cobrindo dimensão sem dado
(2 dimensões distintas não testadas antes: `renda_variavel`, `privados`) e
período fora do disponível (1 caso, via linguagem natural).

Verificação final: `cd services/prisma-api && source ../../.venv/bin/activate && python -m pytest -q` → todos passam, incluindo os 3 novos, sem regressão (baseline 226 passed/6 skipped).

## Critérios de conclusão

- [ ] `services/prisma-api/tests/test_copiloto_cenarios_gestor.py` tem o bloco `# --- H.` com 3 funções de teste
- [ ] `python -m pytest tests/test_copiloto_cenarios_gestor.py -v` → 11/11 passam
- [ ] `python -m pytest services/prisma-api -q` → sem regressão (baseline 226 passed/6 skipped)
- [ ] Nenhum arquivo de produção foi modificado (`git status`)
- [ ] `test_agent_db_integration.py` não foi tocado nem duplicado
- [ ] `plans/README.md` — SKIP se dispatchado via `execute`

## STOP conditions

Pare e reporte (não improvise) se:

- Qualquer teste da Categoria H revelar que o sistema INVENTA dado pra uma
  dimensão/período que não existe (em vez de avisar e cair no fallback) —
  isso é alucinação em conteúdo financeiro, reporte com prioridade alta,
  não tente corrigir dentro deste plano de testes.
- O teste `test_pergunta_periodo_fora_do_disponivel_avisa_em_vez_de_inventar`
  levantar uma exceção não tratada — pare e reporte o traceback completo.
- `DIMENSOES_VALIDAS` não tiver mais `renda_variavel`/`privados` (drift no
  código desde que este plano foi escrito) — pare e reporte quais
  dimensões existem agora, ajuste os nomes só depois de confirmado.

## Notas de manutenção

- As dimensões `supergrupo`, `vencimento`, `renda_fixa`, `ativos` continuam
  sem teste de fallback dedicado depois deste plano — mesma lacuna
  genérica, não é bloqueante (o comportamento é idêntico entre todas as
  dimensões não-estrategia, então `renda_variavel`/`privados` já dão
  cobertura representativa do caminho de código compartilhado).
- Fecha a Categoria H; depois deste plano, todas as 10 categorias da spec
  original (`docs/superpowers/specs/2026-07-20-copiloto-cenarios-gestor-design.md`)
  têm teste formal — I (auditoria) continua só referenciada em
  `test_analisar_endpoint.py` (plano 002), por design (não duplicar).
