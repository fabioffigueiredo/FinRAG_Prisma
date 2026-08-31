# Conjunto de avaliação do Radar

O classificador `Kenpache/finbert-multilingual-v2` permanece **desativado** em produção até concluir este gate.

Crie `radar_sentiment_pt_en.jsonl` a partir de manchetes públicas, sem corpo integral de notícia. Cada linha deve conter:

```json
{"titulo":"Banco Central mantém a taxa de juros","idioma":"pt","sentimento":"neutro","revisado_por":"identificador-do-revisor","revisado_em":"2026-08-31"}
```

Requisitos de promoção:

1. Pelo menos 100 manchetes, com no mínimo 50 em português e 50 em inglês.
2. Todas as etiquetas revisadas por humanos, com revisor e data registrados.
3. Executar `./.venv/bin/python scripts/avaliar_radar.py data/eval/radar_sentiment_pt_en.jsonl --baseline <resultado-finnlp.json>`.
4. O novo candidato precisa superar o macro-F1 do FinNLP atual e manter resultado aceitável em ambos os idiomas. O arquivo de baseline precisa registrar método, versão e macro-F1.

Enquanto qualquer requisito faltar, `PRISMA_RADAR_SENTIMENT_ENABLED` fica em `0` e o Radar público informa indisponibilidade em vez de sentimento ou sinal inventado.
