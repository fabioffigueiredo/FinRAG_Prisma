# Métricas de recuperação (RAG)

Conjunto de 8 *golden queries* do domínio; fonte esperada no top-4.
Reproduza com `python scripts/avaliar_rag.py` (API no ar).

**Hit@4 = 100%** · **MRR = 0.48**

| Pergunta | Fonte esperada | Posição |
|---|---|:--:|
| O que significa alpha e beta? | `03_glossario_benchmark` | top-2 |
| Como é calculada a contribuição de cada ativo? | `01_metodologia_atribuicao` | top-2 |
| O que é a estratégia de crédito privado? | `02_taxonomia_estrategias` | top-4 |
| Por que o varejo pesou no resultado? | `noticia:n07` | top-4 |
| Como o setor bancário contribuiu? | `noticia:n05` | top-3 |
| O que aconteceu com o câmbio no período? | `noticia:n08` | top-2 |
| Qual foi o retorno do fundo Alfa? | `dados:ALFA-33` | top-1 |
| Como funciona o benchmark do fundo? | `03_glossario_benchmark` | top-2 |

> Recuperação com embeddings `bge-m3` (1024-d) sobre regras de atribuição + notícias classificadas + dados do fundo. Guardrail de injeção e de escopo aplicados após a recuperação.
