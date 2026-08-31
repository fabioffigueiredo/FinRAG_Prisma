"""Pipeline auditável para o Radar de Mercado.

O Radar não é um motor de recomendação. Ele coleta manchetes públicas,
aplica filtros determinísticos e só agrega itens que passaram pelo
classificador local com confiança suficiente. Conteúdo integral de portais
nunca é persistido nem devolvido pela API.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol


MODEL_ID = "Kenpache/finbert-multilingual-v2"
MODEL_REVISION = os.environ.get(
    "PRISMA_RADAR_MODEL_REVISION", "d6a74c217b67aadca64851af2db86514074d25a6"
)
MIN_CONFIDENCE = float(os.environ.get("PRISMA_RADAR_MIN_CONFIDENCE", "0.80"))
MAX_AGE_HOURS = int(os.environ.get("PRISMA_RADAR_MAX_AGE_HOURS", "24"))

# Intencionalmente conservadora. Uma notícia fora desta taxonomia não vira
# "sinal de mercado" só porque o classificador reconheceu uma emoção.
RELEVANCE_TERMS = {
    "juros", "selic", "inflação", "inflacao", "cdi", "banco central", "fed",
    "bond", "bonds", "yield", "credit", "crédito", "credito", "spread",
    "debênture", "debenture", "ações", "acoes", "bolsa", "ibovespa", "equity",
    "stocks", "stock market", "câmbio", "cambio", "dólar", "dolar", "fx",
    "commodities", "petróleo", "petroleo", "oil", "brent", "mercado financeiro",
    "financial market", "fundos", "funds", "economia", "economy", "gdp",
}


class SentimentClassifier(Protocol):
    model_version: str

    def classify(self, text: str) -> tuple[str, float]: ...


class LocalFinbertClassifier:
    """Carregamento preguiçoso, fixado por revisão e somente quando habilitado.

    A imagem de produção não baixa modelo implicitamente durante testes. A
    ativação explícita por variável é um gate de operação e de avaliação.
    """

    model_version = f"{MODEL_ID}@{MODEL_REVISION}"

    def __init__(self) -> None:
        self._pipeline: Any | None = None

    def _get_pipeline(self):
        if self._pipeline is None:
            from huggingface_hub import hf_hub_download
            from transformers import AutoModelForSequenceClassification, PreTrainedTokenizerFast, pipeline

            # O repositório fixa `TokenizersBackend`, classe ainda não
            # exposta por algumas versões estáveis do Transformers. Criamos
            # o tokenizer fast diretamente a partir do artefato versionado,
            # mantendo a revisão e os tokens especiais explícitos.
            tokenizer_path = hf_hub_download(MODEL_ID, "tokenizer.json", revision=MODEL_REVISION)
            tokenizer = PreTrainedTokenizerFast(
                tokenizer_file=tokenizer_path,
                bos_token="<bos>", cls_token="<bos>", eos_token="<eos>", sep_token="<eos>",
                pad_token="<pad>", unk_token="<unk>", mask_token="<mask>",
            )
            model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
            self._pipeline = pipeline(
                "text-classification",
                model=model,
                tokenizer=tokenizer,
                device=-1,
            )
        return self._pipeline

    def classify(self, text: str) -> tuple[str, float]:
        result = self._get_pipeline()(text[:2048], truncation=True, max_length=512)[0]
        label = str(result.get("label", "")).lower()
        normalized = {
            "positive": "positivo", "negative": "negativo", "neutral": "neutro",
            "positivo": "positivo", "negativo": "negativo", "neutro": "neutro",
        }.get(label)
        if normalized is None:
            raise ValueError(f"rótulo de sentimento desconhecido: {label}")
        return normalized, round(float(result.get("score", 0.0)), 4)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _is_relevant(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(term in normalized for term in RELEVANCE_TERMS)


def _fingerprint(entry: dict[str, Any]) -> str:
    canonical = (entry.get("link") or entry.get("title") or "").strip().lower()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _groq_tiebreak(text: str) -> tuple[str, str] | None:
    """Desempate de baixo impacto. Sem chave, falha fechada em revisão.

    A confiança do LLM não é tratada como probabilidade calibrada. Por isso
    resultados desta etapa ficam visíveis como revisão assistida, mas não
    entram no agregado nem nos sinais.
    """
    if not os.environ.get("GROQ_API_KEY"):
        return None
    from llm import get_backend

    prompt = (
        "Classifique o sentimento de uma manchete financeira pública. "
        "Responda somente JSON válido: {\"sentimento\":\"positivo|negativo|neutro\"}. "
        "Não faça recomendação e não explique.\n\nManchete: " + text[:900]
    )
    try:
        raw = get_backend("groq").generate(prompt, temperature=0, max_tokens=24)
        parsed = json.loads(raw)
        sentiment = parsed.get("sentimento")
        if sentiment in {"positivo", "negativo", "neutro"}:
            return sentiment, "groq-desempate"
    except Exception:  # noqa: BLE001 - indisponibilidade não vira classificação
        return None
    return None


def classify_entries(
    entries: list[dict[str, Any]],
    *,
    classifier: SentimentClassifier | None,
    now: datetime | None = None,
    max_age_hours: int = MAX_AGE_HOURS,
) -> list[dict[str, Any]]:
    """Transforma RSS em registros públicos mínimos e rastreáveis."""
    now = now or _utc_now()
    cutoff = now - timedelta(hours=max_age_hours)
    seen: set[str] = set()
    output: list[dict[str, Any]] = []

    for entry in entries:
        title = (entry.get("title") or "").strip()
        published_at = _parse_datetime(entry.get("published_at"))
        fingerprint = _fingerprint(entry)
        if not title or not published_at or published_at < cutoff or fingerprint in seen:
            continue
        seen.add(fingerprint)

        text = f"{title}. {(entry.get('summary') or '')}".strip()
        relevant = _is_relevant(text)
        state = "pendente_revisao"
        sentiment: str | None = None
        confidence: float | None = None
        classifier_name: str | None = None
        eligible = False

        if relevant and classifier is not None:
            try:
                sentiment, confidence = classifier.classify(text)
                classifier_name = classifier.model_version
                if confidence >= MIN_CONFIDENCE:
                    state = "classificado_local"
                    eligible = True
                else:
                    tiebreak = _groq_tiebreak(text)
                    if tiebreak is not None:
                        sentiment, classifier_name = tiebreak
                        state = "revisao_assistida"
                    else:
                        state = "pendente_revisao"
            except Exception:  # noqa: BLE001 - modelo indisponível é estado, não dado inventado
                state = "pendente_revisao"

        output.append({
            "id": f"rss-{fingerprint[:16]}",
            "fingerprint": fingerprint,
            "titulo": title,
            "link": entry.get("link", ""),
            "portal": entry.get("portal", "fonte pública"),
            "publicada_em": published_at.isoformat(),
            "coletada_em": now.isoformat(),
            "relevante": relevant,
            "estado": state,
            "sentimento": sentiment,
            "confianca": confidence,
            "classificador": classifier_name,
            "estrategia": "Mercado geral",
            "elegivel_agregado": eligible,
            "fonte": "rss",
        })
    return output


def status_for(noticias: list[dict[str, Any]], classifier: SentimentClassifier | None) -> dict[str, Any]:
    eligible = sum(bool(n.get("elegivel_agregado")) for n in noticias)
    return {
        "estado": "disponivel" if eligible else "degradado",
        "modelo": classifier.model_version if classifier else None,
        "elegiveis": eligible,
        "coletadas": len(noticias),
        "motivo": None if eligible else "sem evidência recente classificada com confiança suficiente",
    }
