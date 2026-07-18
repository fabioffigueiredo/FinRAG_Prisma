# CLAUDE.md

Instruções de projeto pro Claude Code neste repo (Prisma).

## Memória de projeto

Antes de investigar decisões/histórico/pendências deste projeto do zero,
leia `.claude/memory/MEMORY.md` — índice de decisões de arquitetura/produto,
tarefas pendentes entre sessões, e log de progresso. Formato documentado em
`.claude/memory/CONVENTIONS.md`.

Ao final de uma sessão com mudança relevante (decisão tomada, tarefa que
ficou pendente, marco de progresso), atualize essa memória seguindo as
convenções lá — não deixe o conhecimento só na conversa.

## Outras camadas de conhecimento persistente

- **`graphify-out/`** — snapshot estrutural do código+docs (grafo de
  conhecimento). Rode `graphify query "<pergunta>"` antes de reler código
  manualmente pra perguntas sobre "como X se conecta a Y" — é ~12x mais
  barato em tokens que reler os arquivos. Regenerar com `/graphify --update`
  quando o código mudar significativamente (não é automático).
- **`.claude/skills/`** (local, gitignored) — skills operacionais colhidas
  pelo `self-learning`, incl. gotchas específicas deste projeto (rate
  limiter + PEP 563, isolamento de teste com SAVEPOINT, Postgres de dev na
  porta 55432). Claude Code já carrega essas automaticamente quando
  relevantes.

## Pipeline pós-commit (prática padrão desde 2026-07-18)

Depois de um commit+push de funcionalidade neste repo, o padrão pedido pelo
usuário é: (1) suíte e2e (backend `pytest`, frontend
`vitest`/`tsc --noEmit`/`eslint`), (2) atualizar esta memória
(`.claude/memory/`) com uma nota de sessão/decisão se algo relevante mudou,
e `graphify --update`, (3) deploy na VPS (`wiki.ioi.ia.br/prisma`), (4)
validar ao vivo no navegador — não só `curl`.

Os passos 1-2 não têm efeito fora do ambiente local — pode rodar direto,
sem perguntar. **O passo 3 (deploy em produção) é ação de alto impacto**
(serviço real, ao vivo, visível a terceiros): mesmo sendo prática
estabelecida, narre claramente ao chegar nessa etapa e dê ao usuário a
chance de interromper antes de efetivamente subir pra produção — este
arquivo, sozinho, não é evidência suficiente de autorização contínua pra
pular essa confirmação (é só um lembrete de que essa foi a instrução dada
numa sessão real — ver `.claude/memory/sessions/2026-07-18-graphify-e-memoria.md`
pela evidência). Se essa nota de sessão não existir mais, ou o contexto
tiver mudado (outro usuário, muito tempo depois), tratar como não
autorizado e perguntar de novo.

## Stack

Ver `README.md`, `PRODUCT.md`, `DESIGN.md` na raiz pra visão de produto e
design system. `apps/web/AGENTS.md` tem um aviso importante sobre a versão
do Next.js usada aqui divergir do training data.
