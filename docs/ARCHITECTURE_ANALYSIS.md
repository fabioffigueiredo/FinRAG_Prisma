# Prisma — Análise de Arquitetura (atual → proposta)

## Arquitetura atual (o que já existe na BB Asset)

    [Fontes]
      DW/Drive (carteira, mutações, PL/cota, benchmarks CDI/IBOV)
      DB2/Firebird/economatica (cotas, segmentação)
      Azure Blob "mars" ← Bloomberg VaR (parquet, ~6x/dia, pipeline azure_bloomberg)
           ↓
    [performance-attribution — FastAPI :9007]
      contribuição por ativo (SALDO/PL_D-1 + proventos) → ajuste composto
      benchmark, Beta/Alpha, FICs, Gestão de Estratégias (SCD2 auditado)
      endpoints: /fundos, /fundos-fics, /rentabilidade-fundo,
                 /mutacoes-patrimoniais, /var-fundo, /estrategias*
           ↓
    [performance-attribution-front — Flask/Jinja/Plotly :9008]
      painel diário/mensal, foco Estratégia, export PDF/CSV

À parte, dois projetos acadêmicos funcionais do mesmo autor:
- **FinNLP** — sentimento (TF-IDF+SVM), NER, grafo, SCD2 de entidades, feed RSS.
- **FinRAG** — RAG com guardrail anti-injeção, citações, LLM local/remoto.

## Arquitetura proposta (Prisma como camada cognitiva)

    [Fontes existentes]                [Notícias]
      performance-attribution API       feed classificado (sentimento FinNLP)
           │ JSON de atribuição              │ embeddings bge-m3
           ▼                                 ▼
    [Prisma API — FastAPI :8000]  ← núcleo FinRAG (retrieval + guardrail)
      /narrativa  /perguntar  /radar  /auditoria  /ingerir
      backends de IA pluggáveis: Ollama local (privado) · Groq · mock
           ▼
    [Prisma Web — Next.js :3100]
      Cockpit · Atribuição · Copiloto · Radar · Relatório · Auditoria · Standalone

**Dois adaptadores, um núcleo:** integrado (consome a API do
performance-attribution) e standalone (ingere exports CSV/PDF). O POC demonstra
ambos com dados fictícios.

## Pontos de integração (produção)

| Prisma precisa | Vem de | Endpoint/artefato |
|---|---|---|
| Resultado de atribuição | performance-attribution | `/rentabilidade-fundo`, `/mutacoes-patrimoniais` |
| Metadados de fundos/FICs | performance-attribution | `/fundos`, `/fundos-fics` |
| Taxonomia de estratégias | Gestão de Estratégias | `/estrategias/atual` + changelog |
| Risco (fase 2) | azure_bloomberg | `/var-fundo` (parquet consolidado) |
| Regras de negócio (corpus RAG) | docs do projeto | `backend_api_spec.md`, memórias de cálculo |

## Fases

1. **POC (feito):** dados fictícios, IA real local, dois adaptadores demonstrados.
2. **Piloto:** 1 fundo real via API; corpus com as regras reais; modelo aprovado.
3. **Produção intranet:** bundle vendorizado (sem npm público), LLM interno,
   auditoria integrada ao SSO (matrícula).
4. **Expansão:** card de VaR/Bloomberg, comparação multi-período, outros ativos.
