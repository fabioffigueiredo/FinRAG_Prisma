# Prisma — Modelo de Negócio

## Uma frase
O Prisma transforma a atribuição de performance em **narrativa auditável**: explica, em
linguagem natural e fundamentada, de onde veio o retorno de cada fundo. Pluga no
Performance-Attribution ou roda sozinho.

## Problema
A atribuição de performance entrega **números** (contribuição por ativo/estratégia vs
benchmark). Traduzir isso em **comentário de fundo** — o texto que vai para o gestor, o
comitê e o cliente — ainda é feito **à mão**, a cada fechamento, sem padronização e sem
trilha de auditoria. É lento, inconsistente e difícil de escalar para dezenas de fundos.

## Solução
Uma camada cognitiva que lê o resultado da atribuição e:
1. **Explica** o resultado em 1 parágrafo fundamentado (narrativa gerada);
2. **Responde** perguntas sobre o fundo (Q&A com RAG) com **citações** às regras;
3. **Protege** contra manipulação (guardrail anti-injeção) e roda em **modo privado/offline**.

## Arquitetura de produto: um núcleo, dois adaptadores
- **Integrado** — consome a API do Performance-Attribution (BB Asset) e explica os números
  que já existem.
- **Standalone** — ingere exports (CSV/PDF) e roda sem integração.
Mesma experiência; muda só o adaptador de dados. É a modularidade que atende à demanda do
cliente sem reescrever o produto.

## Segmentos de cliente
- **Wedge inicial:** BB Asset (há um champion interno e o Performance-Attribution já entregue).
- **Expansão:** gestoras de recursos e administradores de fundos (Brasil), áreas de
  performance/produtos e relações com investidores.

## Proposta de valor
- **Tempo:** horas de analista economizadas por fechamento (comentário automatizado).
- **Consistência e auditoria:** todo texto é rastreável às regras e aos números.
- **Compliance/privacidade:** modo 100% local (Ollama) — nenhum dado sai da máquina;
  aderente a LGPD e ao apetite de risco de banco.
- **PT-BR financeiro:** afinado ao vocabulário do mercado local.

## Empacotamento e receita (3 modos = 3 adaptadores)
| Modo | Cliente | Cobrança (hipótese a validar) |
|---|---|---|
| **Módulo integrado** | Quem já tem plataforma de atribuição | Licença anual por plataforma |
| **SaaS standalone** | Gestoras sem plataforma | Por nº de fundos + assentos (mensal) |
| **Enterprise on-prem/intranet** | Bancos (ex.: BB) | Licença recorrente + suporte; modelo de IA aprovado internamente |

**Métrica de valor (north star):** comentários de fundo gerados/aprovados por período e
horas economizadas por analista.

## Diferenciais defensáveis (moat)
- RAG **ancorado nas regras de atribuição** (não é chatbot genérico).
- **Guardrail + auditabilidade** — feito para ambiente regulado.
- **Modo privado/offline** com stack local de qualidade (LLM 8B + embeddings bge-m3).
- Conhecimento de domínio (metodologia de contribuição, FIC, correções de sinal).

## Riscos e mitigações
- **Aprovação de modelo em banco** → arquitetura com backend de LLM **pluggável** (local aprovado).
- **Alucinação** → geração **sempre sobre números que já existem** + citações + temperatura baixa.
- **Restrições de intranet (sem npm/pip público, sem Docker)** → POC roda fora; produção
  empacota bundle e usa mirror interno (Artifactory).

## Roadmap (após o POC)
1. Piloto com 1 fundo real (interno).
2. Geração de comentário no fechamento + export no fluxo de PDF existente.
3. Q&A sobre histórico e comparação entre períodos.
4. Expansão para outras gestoras (SaaS).
