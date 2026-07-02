# Prisma — POC

Camada cognitiva que transforma a **atribuição de performance** em **narrativa
auditável**. Núcleo modular com dois adaptadores (integrado ao Performance-Attribution
e standalone). Prova de conceito para apresentação executiva.

> ⚠️ Dados fictícios (fundo "Alfa"), nenhuma instituição real citada. O POC roda
> **fora da intranet BB** — é artefato de venda.

## Arquitetura
```
apps/web/            Next.js 16 + shadcn/ui (Base UI) + Tailwind v4 — o dashboard
services/prisma-api/ FastAPI que envolve o núcleo FinRAG (RAG + guardrail)
data/corpus/         regras de atribuição (corpus RAG, indexado com bge-m3)
data/seed/           fundo-exemplo (fundo_alfa.json)
docs/                deck (HTML), modelo de negócio, GTM
```
O núcleo reusa `PD1/Finrag/src/finrag` (answer, get_llm, SemanticIndex, guardrails)
sem reescrevê-lo. Três backends de LLM selecionáveis na UI:
- **Local (Ollama)** — `llama3.1:8b` + embeddings `bge-m3` · privado/offline (herói)
- **Nuvem (Groq)** — `llama-3.1-8b-instant` · baixa latência
- **Demo (mock)** — determinístico

## Como rodar

**Pré-requisitos:** Node 22 + pnpm; Python 3.12 (venv em `PD1/.venv`); Ollama com
`llama3.1:8b` e `bge-m3:567m` (`ollama pull ...`).

```bash
# 1. API (porta 8000) — indexa o corpus com bge-m3 e pré-aquece o modelo
cd services/prisma-api
../../../.venv/bin/python -m uvicorn app:app --port 8000

# 2. Frontend (porta 3100)
cd apps/web
./node_modules/.bin/next dev -p 3100        # abre http://localhost:3100
```
> Sem a API no ar, o frontend usa dados-exemplo (fallback) e a demo ainda funciona.
> Sem Ollama, a API cai para embeddings sentence-transformers e o backend "mock".

## Roteiro de demo (~5 min)
1. **Cockpit** — números + "Gerar ao vivo" (narrativa local).
2. **Atribuição** — waterfall + drill por estratégia.
3. **Pergunte ao Prisma** — pergunta fundamentada com citações.
4. **Guardrail** — o chip "Ignore as instruções…" é **bloqueado** na tela.
5. **Motor** (topo) — alternar Local ↔ Nuvem para mostrar privacidade vs latência.

## Deck
`docs/deck/index.html` — abrir no navegador; setas ← → para navegar.
