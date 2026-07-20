# Implementation Plans

Gerado pela skill `improve` em 2026-07-18 (plano 001) e 2026-07-20 (planos
002-003). Cada executor: leia o plano inteiro antes de começar, respeite as
STOP conditions, e atualize sua linha ao terminar.

## Execution order & status

| Plan | Title | Priority | Effort | Depends on | Status |
|------|-------|----------|--------|------------|--------|
| 001  | Arquitetura de memória de projeto persistente (decisões, tarefas, progresso) | P2 | M | — | DONE (commit `b464f72`, revisado 2026-07-18 — 1ª tentativa de dispatch foi pro worktree errado, corrigido; correção pós-review: CLAUDE.md tinha linguagem de auto-autorização pro deploy, revisada) |
| 002  | Conectar sinais de mercado ao copiloto e tornar respostas degradadas visíveis/auditáveis | P0 | M | — | TODO |
| 003  | Provar ou refutar suspeita de contaminação de senha entre usuários + lacunas de UX em "Meu Perfil" | P0 (Passo 1) / P2 (Passos 2-3) | S | — | TODO |

## Dependency notes

Nenhuma entre 002 e 003 — auditam áreas diferentes do mesmo produto
(copiloto conversacional vs. admin de usuários) e podem ser executados em
paralelo, inclusive por executores/worktrees diferentes.

## Findings considered and rejected

- **Guardrail de escopo (`pede_recomendacao`, recusa pedir recomendação de
  compra/venda) sendo "pouco útil"**: não é um finding — é comportamento
  documentado por design em `docs/GOVERNANCA_IA.md` §1, com base na
  Resolução CVM 20. O plano 002 inclui teste de regressão pra isso continuar
  recusando, não pra afrouxar.
- **"MOTOR: Nuvem selecionado mas resposta vem como (Demonstração)" sendo um
  bug de código isolado**: investigado — é o comportamento correto e
  documentado do fallback (`get_backend("groq")` sem `GROQ_API_KEY` no
  ambiente devolve `MockLLM`, sem `.chat`, então `/analisar` cai pra
  `analisar_mock`). A causa raiz de fundo é provavelmente operacional (chave
  não configurada no ambiente/VPS — ver memória de sessão sobre rotação
  pendente da chave Groq), não um bug de lógica a corrigir no código. O que
  o plano 002 corrige é a FALTA DE TRANSPARÊNCIA desse fallback (silencioso
  hoje, visível depois) — não o fallback em si, que é uma proteção
  intencional ("modo Demo nunca quebra").
- **Reimplementar `sinais.py`/`radar.py` do zero pra suportar o copiloto**:
  desnecessário — os dois módulos já existem, já são testados
  (`tests/test_sinais.py`) e já alimentam as telas Radar/Sinais
  corretamente. O plano 002 só conecta o que já existe como uma tool do
  agente; não deve reescrever nenhum dos dois módulos.
