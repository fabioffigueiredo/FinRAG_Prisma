# Implementation Plans

Gerado pela skill `improve` em 2026-07-18 (plano 001) e 2026-07-20 (planos
002-003). Cada executor: leia o plano inteiro antes de começar, respeite as
STOP conditions, e atualize sua linha ao terminar.

## Execution order & status

| Plan | Title | Priority | Effort | Depends on | Status |
|------|-------|----------|--------|------------|--------|
| 001  | Arquitetura de memória de projeto persistente (decisões, tarefas, progresso) | P2 | M | — | DONE (commit `b464f72`, revisado 2026-07-18 — 1ª tentativa de dispatch foi pro worktree errado, corrigido; correção pós-review: CLAUDE.md tinha linguagem de auto-autorização pro deploy, revisada) |
| 002  | Conectar sinais de mercado ao copiloto e tornar respostas degradadas visíveis/auditáveis | P0 | M | — | DONE (branch `advisor/002-copiloto-sinais-mercado`, worktree `~/Projetos/prisma-worktrees/plan-002`, commits `27b0332`..`e5cd494`, revisado 2026-07-20 — critérios re-executados pelo revisor, não só o relatório do executor: suíte completa 194 passed/6 skipped sem regressão, `tsc --noEmit` limpo, diff lido linha a linha, testes novos auditados e confirmados não-triviais. Não mergeado — decisão do usuário.) |
| 003  | Provar ou refutar suspeita de contaminação de senha entre usuários + lacunas de UX em "Meu Perfil" | P0 (Passo 1) / P2 (Passos 2-3) | S | — | DONE (branch `advisor/003-isolamento-senha-usuarios`, worktree `~/Projetos/prisma-worktrees/plan-003`, commits `73dccee`..`e19ac4a`, revisado 2026-07-20 — as 3 suspeitas testadas com reprodução HTTP end-to-end real (não só hash direto): **REFUTADAS** as 3 — contaminação de senha entre usuários, vazamento via revogar-sessão+trocar-senha, e divergência de papel na criação. Passo 3 (badge de papel + link "Gerenciar usuários" em Meu Perfil) implementado, pequeno, `tsc`/`eslint` limpos. Suíte completa 186 passed/5 skipped sem regressão. Não mergeado — decisão do usuário.) |
| 004  | Catálogo amplo de cenários de gestor como suíte de testes do copiloto | P1 | M | 002, 005, 006 | IN PROGRESS (worktree `~/Projetos/prisma-worktrees/plan-004`, teste criado, NÃO commitado ainda — 7/8 passam depois do cherry-pick do 005; falta o 006 pra Categoria D destravar o 8º) |
| 005  | Fechar lacunas de fraseado no guardrail de recomendação (escopo.py) | P0 | S | — | DONE (branch `advisor/005-guardrail-recomendacao`, worktree `~/Projetos/prisma-worktrees/plan-005`, commit `eaf3b0c`, revisado 2026-07-20 — critérios re-executados: 196 passed/6 skipped sem regressão, diff idêntico ao plano, e sondagem adversarial própria do revisor com 8 frases não previstas no plano não achou nenhum falso positivo. Um gap residual novo achado na sondagem — "devo aportar mais agora?" ainda escapa — registrado como cauda esperada (nota de manutenção do próprio plano já previa isso), não bloqueia aprovação. Não mergeado. Cherry-picked (commit `8fdb9f3`) pra dentro da worktree do plano 004 pra destravá-lo.) |
| 006  | `analisar_mock` avisa quando pergunta cita fundo inexistente em vez de trocar de fundo silenciosamente | P2 | S | — | TODO |

## Dependency notes

Nenhuma entre 002 e 003 — auditam áreas diferentes do mesmo produto
(copiloto conversacional vs. admin de usuários) e podem ser executados em
paralelo, inclusive por executores/worktrees diferentes.

004 depende de 002: a categoria B do catálogo (sinais de mercado) só faz
sentido depois que `obter_sinais_mercado` existir em `agent.py`. Execute 002
antes de 004; 003 é independente dos dois e pode rodar em qualquer ordem.

004 está bloqueado por 005: a execução do 004 encontrou um achado real
(guardrail de recomendação com lacunas de fraseado coloquial) e parou por
instrução própria do plano em vez de afrouxar o teste. 005 corrige a causa
raiz em `escopo.py`; depois disso, retome 004 a partir de onde parou (o
teste `test_copiloto_cenarios_gestor.py` já criado na worktree do 004 deve
passar sem alteração).

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
- **Suspeita de contaminação de senha entre usuários** (plano 003, Passo
  1/1b): investigada com reprodução HTTP end-to-end real (login de verdade
  com senha antiga/nova, não só comparação de hash). **Refutada** — trocar
  a senha de um usuário não afeta outro, a senha antiga deixa de funcionar
  corretamente, e revogar sessão + trocar senha de outro usuário não altera
  a senha do gestor logado. Não há bug — a narração original era confusão
  de teste manual, como suspeitado desde a escrita do plano.
- **Papel do usuário criado divergindo do pedido no formulário** (plano
  003, Passo 2): investigada, também refutada — `POST /usuarios` com
  `papel: "analista"` cria exatamente com esse papel.
