# Validação do Radar

O Radar é um experimento de contexto de notícias. Não produz recomendação, previsão nem classificação de estratégia.

## Estado atual

O pipeline está implementado, mas a classificação automática está desabilitada no ambiente hospedado. O modelo candidato é `Kenpache/finbert-multilingual-v2` na revisão `d6a74c217b67aadca64851af2db86514074d25a6`. Um carregamento local e inferência de fumaça verificaram a integração técnica. Isso não é uma validação de qualidade.

## Gate de promoção

Antes de habilitar o modelo, o conjunto de avaliação precisa ter pelo menos 100 manchetes públicas revisadas manualmente, divididas entre português e inglês. O script `scripts/avaliar_radar.py` bloqueia conjuntos incompletos e mede macro-F1. A promoção exige superar o FinNLP atual em macro-F1, registrar a versão do baseline e revisar o resultado em ambos os idiomas.

## Comportamento seguro

Cada lote conserva somente título, URL, fonte, data de publicação, hora de coleta, versão do classificador, confiança e estado. Itens duplicados, sem data, mais antigos que 24 horas ou não relevantes são descartados. Baixa confiança ou falha local/nuvem vira `pendente de revisão`; esses itens não entram em agregados ou sinais. A nuvem recebe apenas a manchete pública quando o desempate está explicitamente configurado.
