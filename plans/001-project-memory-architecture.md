# Plan 001: Arquitetura de memória de projeto persistente (decisões, tarefas, progresso)

> **Executor instructions**: Siga este plano passo a passo. Rode cada comando
> de verificação e confirme o resultado esperado antes de seguir pro próximo
> passo. Se algo na seção "STOP conditions" acontecer, pare e reporte — não
> improvise. Ao terminar, atualize a linha de status deste plano em
> `plans/README.md` — a menos que quem te despachou já tenha dito que cuida
> do índice.
>
> **Drift check (rodar primeiro)**: `git diff --stat be4cf0e..HEAD -- .gitignore CLAUDE.md .claude/`
> Se `.gitignore` mudou desde que este plano foi escrito, releia a seção
> "Current state" antes de prosseguir — o design inteiro depende de
> `.claude/` e `.agents/` continuarem gitignored (ver STOP conditions).

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Planned at**: commit `be4cf0e`, 2026-07-18

## Why this matters

Hoje o projeto Prisma tem duas camadas de persistência entre sessões, mas
nenhuma cobre decisões/tarefas/progresso:

1. **graphify** (`graphify-out/`) — snapshot ESTRUTURAL do código+docs
   (1.708 nós, 3.803 arestas, 116 comunidades nesta execução). Caro de
   regerar (~514k tokens nesta rodada) e não é um log vivo — é uma foto.
2. **self-learning** (`.agents/skills/self-learning/`) — já colhe
   PROCEDIMENTOS/gotchas operacionais como skills (`fastapi-slowapi-future-annotations`,
   `prisma-test-commit-isolation`, `prisma-dev-postgres-setup`,
   `shadcn-command-dialog-needs-command-wrapper` já existem). Funciona bem
   pro que se propõe.

Falta a camada que o próprio `self-learning` presume existir: "*se seu
harness tem um MEMORY.md index, registre lá*" (SKILL.md, seção "Skill,
memory, or skip?"). Esse índice não existe. O resultado, visto nesta própria
sessão: uma inconsistência de paleta de cor entre `DESIGN.md` e
`apps/web/DESIGN.md` (uma delas descrevia uma paleta abandonada há 9 dias)
só foi descoberta porque o grafo apontou a aresta AMBIGUOUS — sem memória
viva, cada sessão futura vai precisar re-investigar `git log` pra descobrir
fatos assim de novo, gastando tokens que uma nota de 5 linhas evitaria.

Este plano cria essa terceira camada — decisões (com razão), tarefas
pendentes entre sessões, e um log leve de progresso — usando o formato
Obsidian Flavored Markdown (`kepano/obsidian-skills`) para notas atômicas
com frontmatter/wikilinks/callouts, e explicita a fronteira com as outras
duas camadas pra não duplicar esforço.

## Current state

### As três camadas hoje

- `graphify-out/graph.json`, `GRAPH_REPORT.md` — gerados nesta sessão,
  cobrem código+docs+screenshots. **Não gitignored** (verificado:
  `git check-ignore -v graphify-out/graph.json` retorna exit 1 — não
  ignorado). É um artefato grande (graph.json ~1.8MB, graph.html ~1.7MB) e
  regenerável — candidato a `.gitignore`, ver Step 7.
- `.claude/skills/` (8 skills incl. `improve`, `find-skills`, e 4 skills de
  gotcha colhidas pelo self-learning) e `.agents/skills/self-learning/`
  (instalado via `skills-lock.json`, fonte `kulaxyz/self-learning-skills`).
  **Ambos gitignored** — `.gitignore:26-27` (`.claude/` e `.agents/`), sob o
  comentário `# Ferramentas/editores locais`, no mesmo grupo de `.vscode/`
  e `.idea/`. Confirmado via `git check-ignore -v`: nenhum arquivo sob essas
  duas pastas está rastreado.
- **Não existe `CLAUDE.md`/`AGENTS.md`/`CONTEXT.md` na raiz do repo.** Só
  existe `apps/web/CLAUDE.md` (uma linha, `@AGENTS.md`) e
  `apps/web/AGENTS.md` (aviso de versão do Next.js) — escopo só do
  frontend, nada sobre memória/decisões/tarefas.

### Por que a exclusão do `.claude/`/`.agents/` no `.gitignore` importa pro design

`.gitignore:24-28`:
```
# Ferramentas/editores locais
.claude/
.agents/
skills-lock.json
.vscode/
.idea/
```

Isso é deliberado, não um bug — trata config de tooling de IA como
preferência de editor local, nunca versionada. A nova camada de memória
**deve seguir essa mesma convenção** (viver dentro de `.claude/`, herdar o
gitignore existente) em vez de criar uma pasta visível na raiz: evita
reabrir a questão de "isso deveria ir pro GitHub público?" (que não é desta
plano decidir) e mantém consistência com o padrão já estabelecido pros
skills. Ver STOP conditions se essa entrada do `.gitignore` tiver sido
removida.

### Convenções do Obsidian Flavored Markdown (de `kepano/obsidian-skills`)

Verificado via `gh api repos/kepano/obsidian-skills/contents/...` (repo
público, skill `obsidian-markdown`, MIT-style spec):

- **Frontmatter (properties):** bloco YAML `---` no topo — `tags`,
  `aliases`, mais qualquer propriedade custom (ex.: `status`, `type`).
- **Wikilinks:** `[[Nome da Nota]]` para notas dentro do vault (renomeia
  junto); `[[Nota#Heading]]` pra âncora; `[[Nota|Texto]]` pra label custom.
  Markdown link `[texto](url)` só pra URL externa.
- **Callouts:** `> [!warning]`, `> [!tip]`, `> [!bug]`, etc. — bloco
  destacado com tipo semântico.
- **Embeds:** `![[Nota]]` — não necessário pro uso deste plano (uma nota
  por decisão/tarefa é atômica, sem embed).

Repo também tem `obsidian-bases` (`.base` — view tipo tabela/board sobre
notas com filtro por `property`), útil pra um board de tarefas pendentes,
mas **só renderiza dentro do app Obsidian** — não afeta o Claude Code em
nada. Incluído como opcional no Step 5, não obrigatório.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Instalar skill obsidian-markdown | `npx skills add kepano/obsidian-skills@obsidian-markdown` | `.claude/skills/obsidian-markdown/SKILL.md` existe |
| (Opcional) instalar obsidian-bases | `npx skills add kepano/obsidian-skills@obsidian-bases` | `.claude/skills/obsidian-bases/SKILL.md` existe |
| Validar YAML de uma nota | `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]).read().split('---')[1])" <arquivo>` | exit 0, sem exceção |
| Confirmar gitignore ainda cobre .claude/ | `git check-ignore -v .claude/memory/MEMORY.md` | imprime a linha `.gitignore:26:.claude/` |
| Confirmar CLAUDE.md raiz é rastreado | `git check-ignore -v CLAUDE.md` | exit 1 (NÃO ignorado) |

Não há `pnpm install`/`pip install` — este plano só cria arquivos Markdown +
uma entrada de `.gitignore` + um `CLAUDE.md`. Nenhuma dependência de
runtime nova.

## Suggested executor toolkit

- Skill `obsidian-markdown` (instalada no Step 1) — usar pra formatar
  frontmatter/wikilinks/callouts corretamente em toda nota nova.
- Nenhum outro skill do repo precisa ser tocado.

## Scope

**In scope** (únicos arquivos/pastas a criar ou modificar):
- `.claude/memory/MEMORY.md` (criar)
- `.claude/memory/CONVENTIONS.md` (criar)
- `.claude/memory/decisions/*.md` (criar — mínimo 3, ver Step 3)
- `.claude/memory/tasks/*.md` (criar — mínimo 1, ver Step 4)
- `.claude/memory/sessions/*.md` (criar — mínimo 1, ver Step 4)
- `CLAUDE.md` (criar, raiz do repo — **este É rastreado pelo git**)
- `.gitignore` (editar — adicionar `graphify-out/`)
- `.claude/skills/obsidian-markdown/` e opcionalmente
  `.claude/skills/obsidian-bases/` (instalados via `npx skills add`, não
  editados manualmente)

**Out of scope** (não tocar, mesmo parecendo relacionado):
- `.agents/skills/self-learning/` e as 4 skills de gotcha já colhidas —
  funcionam, não duplicar.
- `graphify-out/graph.json`, `GRAPH_REPORT.md`, ou qualquer coisa sob
  `graphify-out/` além de adicioná-lo ao `.gitignore` — não regenerar o
  grafo como parte deste plano.
- `apps/web/CLAUDE.md` / `apps/web/AGENTS.md` — escopo diferente (aviso de
  versão do Next.js), não mesclar com a memória de projeto.
- `PRODUCT.md` (raiz) — o roadmap de negócio ali é público/de produto, não
  é o mesmo que o backlog técnico de `tasks/` deste plano; não migrar um
  pro outro.
- Instalar `obsidian-cli`, `json-canvas`, ou `defuddle` de
  `kepano/obsidian-skills` — não usados por este design (cli exige o app
  Obsidian instalado; canvas é pra diagrama visual; defuddle é scraper de
  página web — nenhum se aplica aqui).
- `DESIGN.md` / `apps/web/DESIGN.md` — já corrigidos numa sessão anterior a
  este plano; só referenciados como worked example no Step 3.

## Git workflow

- Só `CLAUDE.md` (raiz) e `.gitignore` entram num commit — tudo sob
  `.claude/memory/` fica fora do git (herda a exclusão existente de
  `.claude/`).
- Estilo de commit observado no repo (`git log --oneline -10`): conventional
  commits com escopo, ex. `feat(auth): ...`, `fix(deploy): ...`,
  `docs(finrag): ...`. Para este plano: `chore(memory): adiciona CLAUDE.md
  raiz + memória local de projeto` (ou separar em dois commits — um pro
  `CLAUDE.md`, outro pro `.gitignore` — se preferir granularidade).
- Não commitar sem o usuário pedir explicitamente (regra padrão deste
  projeto/sessão) — este plano só descreve os passos; quem executar decide
  se comita ao final ou deixa como working tree pro usuário revisar.

## Steps

### Step 1: Instalar a skill `obsidian-markdown`

```bash
npx skills add kepano/obsidian-skills@obsidian-markdown
```

Se o comando falhar (rede indisponível, `npx skills` não instalado): fallback
manual — buscar o conteúdo direto do GitHub e escrever nos mesmos caminhos:

```bash
mkdir -p .claude/skills/obsidian-markdown/references
gh api repos/kepano/obsidian-skills/contents/skills/obsidian-markdown/SKILL.md --jq '.content' | base64 -d > .claude/skills/obsidian-markdown/SKILL.md
for f in CALLOUTS.md EMBEDS.md PROPERTIES.md; do
  gh api repos/kepano/obsidian-skills/contents/skills/obsidian-markdown/references/$f --jq '.content' | base64 -d > .claude/skills/obsidian-markdown/references/$f
done
```

**Verify**: `test -f .claude/skills/obsidian-markdown/SKILL.md && echo OK` → `OK`

(Opcional) Repetir pra `obsidian-bases` trocando `obsidian-markdown` por
`obsidian-bases` nos dois blocos acima, se quiser o board `.base` do Step 5.

### Step 2: Criar a estrutura de pastas e o índice `MEMORY.md`

```bash
mkdir -p .claude/memory/decisions .claude/memory/tasks .claude/memory/sessions
```

Criar `.claude/memory/MEMORY.md`:

```markdown
# Memória do Projeto Prisma

Índice — uma linha por nota, sem conteúdo aqui. Ordem: mais recente primeiro
dentro de cada seção. Ver `.claude/memory/CONVENTIONS.md` pro formato de
cada tipo de nota.

## Decisões
- [[decisions/2026-07-18-design-doc-drift]] — apps/web/DESIGN.md descrevia paleta ouro/ink abandonada há 9 dias; corrigido pra navy/teal institucional real

## Tarefas pendentes
- [[tasks/finalizar-redesign-ouro-ou-manter-teal]] — decidir se o redesign institucional (navy/teal) é definitivo ou se volta ao ouro documentado em apps/web/DESIGN.md original

## Sessões
- [[sessions/2026-07-18-graphify-e-memoria]] — primeira execução do graphify (1708 nós/3803 arestas) + criação desta camada de memória
```

**Verify**: `test -f .claude/memory/MEMORY.md && wc -l .claude/memory/MEMORY.md` →
arquivo existe, ao menos 8 linhas.

### Step 3: Criar `.claude/memory/CONVENTIONS.md` (schema das notas)

```markdown
# Convenções das notas de memória

Formato: Obsidian Flavored Markdown (skill `obsidian-markdown`). Uma nota
por decisão/tarefa/sessão — nunca um arquivo único crescendo sem limite
(isso é exatamente o anti-padrão que o MEMORY.md do usuário, no nível
global, já evita).

## Frontmatter obrigatório

\`\`\`yaml
---
type: decision | task | session
status: proposed | accepted | superseded   # decisions
       | pending | in-progress | done | blocked   # tasks
       | n/a   # sessions
date: YYYY-MM-DD
tags: [prisma, <area, ex: design-system|auth|finrag|deploy>]
---
\`\`\`

## decisions/<slug>.md

Decisão de arquitetura/produto + a razão (o "porquê", não só o "o quê" —
código já mostra o quê). Seções: `## Decisão`, `## Por quê`,
`## Alternativas descartadas` (se houver). Linkar código/doc relevante com
wikilink relativo por descrição (ex.: `[[../../../DESIGN.md]]` não
funciona fora do Obsidian — preferir caminho relativo normal do repo em
texto, já que este vault não abre arquivos fora de `.claude/memory/`).

## tasks/<slug>.md

Item de backlog que atravessa sessões — não confundir com o `TaskCreate`
efêmero do Claude Code (que é por-conversa). Só o que precisa sobreviver
entre sessões vai aqui. Seções: `## O que falta`, `## Por que ainda não foi
feito` (bloqueio, decisão pendente, prioridade baixa), `## Como retomar`.

## sessions/<data>-<slug>.md

Log leve — não é transcript, é o resumo de uma sessão que valeu a pena
lembrar (mudança grande, decisão tomada, marco). Não criar uma nota por
sessão trivial. Seções: `## O que mudou`, `## Decisões tomadas nesta
sessão` (linka pra decisions/ se aplicável).

## Callouts

Usar `> [!warning]` pra armadilha ainda não virou skill de self-learning,
`> [!tip]` pra atalho, `> [!bug]` pra bug conhecido não resolvido.

## Quando ATUALIZAR vs criar nova nota

Igual ao MEMORY.md pessoal do usuário: se uma decisão for revista, editar a
nota existente (mudar `status: accepted` → `status: superseded`, com uma
linha explicando) em vez de duplicar. `MEMORY.md` (o índice) só recebe uma
linha nova quando a nota é nova — nunca conteúdo direto.

## Fronteira com as outras duas camadas

- **self-learning** (`.agents/skills/self-learning/`) já cobre
  procedimentos/gotchas multi-passo (como rodar migration, onde fica o
  banco, etc.) — isso vira uma *skill*, não uma nota aqui. Se o
  self-learning já capturou, só referencie por nome, não duplique o
  conteúdo.
- **graphify** (`graphify-out/`) é o snapshot estrutural do código — não
  registre "o que o código faz" aqui, isso já está no grafo (mais barato
  de consultar via `graphify query` do que reler uma nota). Registre só o
  que o grafo não sabe: por quê, o que falta, o que já foi tentado.
- **plans/** (esta skill `/improve`) é pra iniciativas maiores, auditadas,
  com plano de execução formal. `tasks/` aqui é pra itens leves,
  ad-hoc — não duplicar um plano formal como task.
```

**Verify**: `test -f .claude/memory/CONVENTIONS.md && grep -c "^## " .claude/memory/CONVENTIONS.md` →
retorna um número ≥ 5.

### Step 4: Semear as notas reais desta sessão (worked examples)

Criar `.claude/memory/decisions/2026-07-18-design-doc-drift.md`:

```markdown
---
type: decision
status: accepted
date: 2026-07-18
tags: [prisma, design-system]
---

# apps/web/DESIGN.md estava descrevendo uma paleta abandonada

## Decisão

`DESIGN.md` (raiz) é a fonte de verdade pra paleta de cor — navy claro
(`#003366`) / teal escuro (`#2dd4bf`), com âmbar (`#fdb913`) como acento
vivo constante. `apps/web/DESIGN.md` foi corrigido pra parar de descrever a
paleta ouro/ink original (`#f0b952`).

## Por quê

`git log` confirma a linha do tempo: POC inicial (`a071377`, 2026-07-02)
tinha `--primary: #f0b952` (ouro). `apps/web/DESIGN.md` foi escrito 1 dia
depois (`42e57e6`, por um colaborador) documentando essa paleta ouro. O
commit `d73f206` ("Redesign institucional", 2026-07-08) TROCOU a paleta pra
navy/teal — mas nunca atualizou `apps/web/DESIGN.md`. `DESIGN.md` (raiz) foi
escrito depois (`0fe5f2d`, 2026-07-17) já documentando a paleta nova
corretamente. `globals.css` hoje bate com `DESIGN.md` (raiz), não com o
`apps/web/DESIGN.md` original.

## Alternativas descartadas

- Aplicar `--primary: #f0b952` no CSS pra "terminar" o redesign ouro que
  `apps/web/DESIGN.md` descrevia — descartado: teria REVERTIDO uma decisão
  deliberada e recente (`d73f206`), não uma tarefa inacabada.
```

Criar `.claude/memory/tasks/finalizar-redesign-ouro-ou-manter-teal.md`:

```markdown
---
type: task
status: pending
date: 2026-07-18
tags: [prisma, design-system]
---

# Confirmar: paleta navy/teal institucional é definitiva?

## O que falta

Nenhuma ação de código — só confirmação do usuário. `apps/web/DESIGN.md` já
foi corrigido pra refletir a paleta navy/teal atual (ver
[[../decisions/2026-07-18-design-doc-drift]]). Se o usuário decidir voltar
pro ouro/ink original em algum momento, essa nota deve virar uma
`decision` nova, não uma edição silenciosa do CSS.

## Por que ainda não foi feito

Não é um bug — é só uma decisão de produto que ninguém confirmou
explicitamente ainda (a troca pra navy/teal aconteceu num commit sem
issue/discussão registrada).

## Como retomar

Perguntar ao usuário se o teal é definitivo antes de qualquer trabalho
visual futuro no dark mode.
```

Criar `.claude/memory/sessions/2026-07-18-graphify-e-memoria.md`:

```markdown
---
type: session
status: n/a
date: 2026-07-18
tags: [prisma, tooling]
---

# Primeira execução do graphify + criação da memória de projeto

## O que mudou

- Primeira execução completa do `/graphify` sobre o repo Prisma: 1.708 nós,
  3.803 arestas, 116 comunidades, 12.8x de redução de tokens por consulta
  (benchmark). Saída em `graphify-out/`.
- Descoberta (via aresta AMBIGUOUS do grafo) e correção da inconsistência
  de paleta entre `DESIGN.md` e `apps/web/DESIGN.md` — ver
  [[../decisions/2026-07-18-design-doc-drift]].
- Criação desta camada de memória (`.claude/memory/`) — plano completo em
  `plans/001-project-memory-architecture.md`.

## Decisões tomadas nesta sessão

- [[../decisions/2026-07-18-design-doc-drift]]
```

**Verify**: `find .claude/memory -name "*.md" | wc -l` → ≥ 6 (MEMORY.md +
CONVENTIONS.md + 3 notas seed).

### Step 5 (opcional): Board `.base` de tarefas pendentes

Só se a skill `obsidian-bases` foi instalada no Step 1. Criar
`.claude/memory/tasks.base`:

```yaml
filters:
  and:
    - 'type == "task"'
views:
  - type: table
    name: "Tarefas pendentes"
    filters:
      and:
        - 'status == "pending" || status == "in-progress"'
    order:
      - file.name
      - status
      - tags
```

Isso só renderiza dentro do app Obsidian (se o usuário abrir
`.claude/memory/` como vault) — não afeta o Claude Code. Pular se o usuário
não usa o app Obsidian.

**Verify**: `python3 -c "import yaml; yaml.safe_load(open('.claude/memory/tasks.base'))" && echo OK` → `OK`

### Step 6: Criar `CLAUDE.md` na raiz do repo

Este arquivo **é rastreado pelo git** (diferente de tudo em `.claude/`).
Conteúdo:

```markdown
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

## Stack

Ver `README.md`, `PRODUCT.md`, `DESIGN.md` na raiz pra visão de produto e
design system. `apps/web/AGENTS.md` tem um aviso importante sobre a versão
do Next.js usada aqui divergir do training data.
```

**Verify**: `git check-ignore -v CLAUDE.md; echo "exit: $?"` → exit 1 (arquivo
NÃO ignorado, confirma que será rastreado).

### Step 7: Adicionar `graphify-out/` ao `.gitignore`

Editar `.gitignore`, adicionar uma seção nova (não misturar com "Ferramentas
locais" — motivo é tamanho/regenerabilidade, não ocultar IA):

```
# graphify — grafo de conhecimento regenerável (grande, refaz com --update)
graphify-out/
```

**Verify**: `git check-ignore -v graphify-out/graph.json` → imprime a nova
linha do `.gitignore`, exit 0.

## Test plan

Não há testes automatizados aplicáveis (arquivos Markdown/YAML, não
código executável). Verificação é estrutural:

- Toda nota nova tem frontmatter YAML válido — testar com o comando da
  tabela "Commands you will need" em cada arquivo de `decisions/`, `tasks/`,
  `sessions/`.
- Nenhuma nota contém valor de segredo — `grep -riE "api[_-]?key|secret|password|token" .claude/memory/ --include="*.md" --include="*.base"` deve retornar só as MENÇÕES de nome de variável (ex. `PRISMA_JWT_SECRET` como texto), nunca um valor.
- `git status --short` depois de todos os steps deve mostrar `CLAUDE.md` e
  `.gitignore` como as únicas mudanças TRACKED — tudo sob `.claude/`
  continua invisível ao `git status` (confirma que herdou o gitignore).

## Done criteria

- [ ] `.claude/skills/obsidian-markdown/SKILL.md` existe
- [ ] `.claude/memory/MEMORY.md` existe com as 3 seções (Decisões, Tarefas
      pendentes, Sessões) e ao menos 1 link cada
- [ ] `.claude/memory/CONVENTIONS.md` existe e documenta os 3 tipos de nota
      + a fronteira com self-learning/graphify/plans
- [ ] `.claude/memory/decisions/`, `tasks/`, `sessions/` têm ao menos 1
      arquivo cada, todos com frontmatter YAML válido
- [ ] `CLAUDE.md` (raiz) existe, referencia `.claude/memory/MEMORY.md`, e
      `git check-ignore -v CLAUDE.md` retorna exit 1 (rastreado)
- [ ] `.gitignore` contém uma entrada `graphify-out/`
- [ ] `grep -riE "api[_-]?key|secret|password|token" .claude/memory/` não
      retorna nenhum valor de segredo (só nomes de variável são aceitáveis)
- [ ] `git status --short` mostra só `CLAUDE.md` e `.gitignore` como
      tracked changes

## STOP conditions

Pare e reporte (não improvise) se:

- `.gitignore` não contém mais as linhas `.claude/`/`.agents/` no momento da
  execução (alguém decidiu tornar esses diretórios públicos entre o
  planejamento e a execução) — o design inteiro deste plano assume que
  `.claude/memory/` fica local; se isso mudou, a pergunta "isso deveria ir
  pro GitHub público?" precisa ser respondida pelo usuário antes de
  continuar, não decidida por você.
- `CLAUDE.md` já existe na raiz (criado independentemente entre o
  planejamento e a execução) — não sobrescrever; mesclar a seção "Memória
  de projeto" nele em vez de substituir o arquivo inteiro.
- `npx skills add` falha E o fallback manual (Step 1) também falha (sem
  acesso de rede a `github.com`) — reporte e pare; não invente o conteúdo
  do SKILL.md de memória.

## Maintenance notes

- Quem manter este projeto depois: `self-learning` continua sendo o lugar
  certo pra gotchas operacionais novas — não redirecionar esse fluxo pra
  `.claude/memory/decisions/`. As duas camadas convivem, ver
  `CONVENTIONS.md`.
- Se o Prisma passar a ter mais de um desenvolvedor, revisitar a decisão de
  manter `.claude/`/`.agents/` fora do git (Step "Current state") — isso é
  uma escolha explícita do usuário, não algo pra este plano decidir.
- `graphify-out/` sendo gitignored significa que um clone novo do repo
  NÃO tem o grafo — quem clonar precisa rodar `/graphify` de novo (ou
  `--update` se já tiver rodado antes localmente). Isso é aceitável dado
  que o grafo é 100% regenerável a partir do código+docs versionados.
