# Prisma — Análise de Arquitetura (atual → proposta)

> Contexto generalizado: o cliente-alvo é uma **grande gestora de recursos** que já
> possui uma **plataforma de atribuição de performance** em produção. Nomes de
> sistemas, fornecedores e endpoints internos foram abstraídos.

## Arquitetura típica existente (lado do cliente)

    [Fontes]
      Data warehouse (carteira, movimentações, PL/cota, benchmarks CDI/IBOV)
      Bases legadas (cotas, segmentação de ativos)
      Provedor de mercado ← risco/VaR (arquivos periódicos)
           ↓
    [Plataforma de atribuição — API REST]
      contribuição por ativo (saldo/PL D-1 + proventos) → ajuste composto
      benchmark, Beta/Alpha, fundos-de-fundos, taxonomia de estratégias auditada
      endpoints de resultado, metadados de fundos e classificação de estratégias
           ↓
    [Painel da plataforma]
      visão diária/mensal por estratégia, export PDF/CSV

À parte, dois projetos funcionais do mesmo autor que originaram o Prisma:
- **FinNLP** — sentimento (TF-IDF+SVM), NER, grafo de entidades, feed de notícias.
- **FinRAG** — RAG com guardrail anti-injeção, citações, LLM local/remoto.

## Arquitetura proposta (Prisma como camada cognitiva)

    [Fontes existentes]                [Notícias]
      API da plataforma de atribuição   feed classificado (sentimento FinNLP)
           │ JSON de atribuição              │ embeddings bge-m3
           ▼                                 ▼
    [Prisma API — FastAPI :8000]  ← núcleo FinRAG (retrieval + guardrail)
      /narrativa  /perguntar  /radar  /auditoria  /ingerir
      backends de IA pluggáveis: Ollama local (privado) · Groq · mock
           ▼
    [Prisma Web — Next.js :3100]
      Cockpit · Atribuição · Copiloto · Radar · Relatório · Auditoria · Standalone

**Dois adaptadores, um núcleo:** integrado (consome a API da plataforma de
atribuição do cliente) e standalone (ingere exports CSV/PDF). O POC demonstra
ambos com dados fictícios.

## Pontos de integração (produção)

| Prisma precisa | Vem de | Artefato |
|---|---|---|
| Resultado de atribuição | plataforma de atribuição | endpoint de rentabilidade/movimentações |
| Metadados de fundos/FICs | plataforma de atribuição | endpoint de fundos |
| Taxonomia de estratégias | módulo de classificação | classificação vigente + changelog |
| Risco (fase 2) | provedor de mercado | série de VaR consolidada |
| Regras de negócio (corpus RAG) | documentação do cliente | especificações e memórias de cálculo |

## Fases

1. **POC (feito):** dados fictícios, IA real local, dois adaptadores demonstrados.
2. **Piloto:** 1 fundo real via API; corpus com as regras reais; modelo aprovado.
3. **Produção em ambiente corporativo restrito:** bundle vendorizado (sem acesso a
   registries públicos), LLM homologado internamente, auditoria integrada ao SSO.
4. **Expansão:** card de risco/VaR, comparação multi-período, outras classes de ativos.
