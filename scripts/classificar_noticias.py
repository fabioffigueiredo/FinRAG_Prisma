"""Classifica as notícias semeadas com o pipeline REAL do FinNLP (TF-IDF+SVM).

Integração FinNLP → Prisma (abordagem C da spec): roda offline, uma vez, e
versiona o resultado — a API nunca depende do FinNLP em runtime.

DECISÃO DE ROTULAGEM (documentada aqui, exigência da spec): o SVM do FinNLP é
treinado no financial_phrasebank (inglês). Rodar `--llm` também rotula cada
notícia com o llama3.1 local (Ollama) em PT. Após inspeção manual da saída,
o campo final `sentimento` usa: SVM por padrão; LLM quando `--llm` for passado
(mantendo `sentimento_svm` como comparativo).

Uso:
    cd prisma && .venv/bin/python scripts/classificar_noticias.py [--llm]
    (dependências extras do pipeline: pip install -r scripts/finnlp_pipeline/requirements-finnlp.txt)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PRISMA = Path(__file__).resolve().parents[1]
FINNLP_DIR = PRISMA / "scripts" / "finnlp_pipeline"
sys.path.insert(0, str(FINNLP_DIR))

SEED = PRISMA / "data" / "seed"
ENTRADA = SEED / "noticias_alfa.json"
SAIDA = SEED / "noticias_alfa_classificadas.json"

MAPA = {"positive": "positivo", "negative": "negativo", "neutral": "neutro",
        "positivo": "positivo", "negativo": "negativo", "neutro": "neutro",
        0: "negativo", 1: "neutro", 2: "positivo"}


def treinar_svm_finnlp():
    """Treina com as funções do FinNLP (vendorizadas em scripts/finnlp_pipeline).
    Aborta com mensagem clara se as dependências extras não estiverem instaladas."""
    try:
        from coleta_preprocessamento import load_phrasebank
        from modelagem_vetorizacao import build_tfidf, train_svm
    except Exception as e:  # noqa: BLE001
        sys.exit(
            f"ERRO: não consegui importar o pipeline do FinNLP em {FINNLP_DIR}: {e}\n"
            "Instale as dependências extras: pip install -r scripts/finnlp_pipeline/requirements-finnlp.txt"
        )
    df = load_phrasebank()                                           # AJUSTAR se assinatura divergir
    textos = df["text"].tolist() if hasattr(df, "columns") else [d["text"] for d in df]
    labels = df["label"].tolist() if hasattr(df, "columns") else [d["label"] for d in df]
    vec_out = build_tfidf(textos)
    vectorizer, X = vec_out if isinstance(vec_out, tuple) else (vec_out, vec_out.transform(textos))
    modelo = train_svm(X, labels)
    return vectorizer, modelo


def rotular_llm(titulo: str, corpo: str) -> str:
    import requests
    prompt = (
        "Classifique o sentimento desta notícia financeira para um fundo de "
        "investimentos. Responda SOMENTE uma palavra: positivo, negativo ou neutro.\n\n"
        f"Notícia: {titulo}. {corpo}"
    )
    r = requests.post("http://localhost:11434/v1/chat/completions", timeout=120, json={
        "model": "llama3.1:8b", "temperature": 0, "max_tokens": 4,
        "messages": [{"role": "user", "content": prompt}],
    })
    r.raise_for_status()
    palavra = r.json()["choices"][0]["message"]["content"].strip().lower()
    for k in ("positivo", "negativo", "neutro"):
        if k in palavra:
            return k
    return "neutro"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="rotular também com llama3.1 local (rótulo final)")
    args = ap.parse_args()

    noticias = json.loads(ENTRADA.read_text(encoding="utf-8"))
    vectorizer, modelo = treinar_svm_finnlp()

    for n in noticias:
        texto = f"{n['titulo']}. {n['corpo']}"
        Xn = vectorizer.transform([texto])
        pred = modelo.predict(Xn)[0]
        conf = 0.0
        if hasattr(modelo, "decision_function"):
            import numpy as np
            margens = np.abs(modelo.decision_function(Xn)).ravel()
            conf = float(round(min(1.0, margens.max() / 2.0), 2))
        n["sentimento_svm"] = MAPA.get(pred, str(pred))
        n["confianca"] = conf
        n["sentimento"] = rotular_llm(n["titulo"], n["corpo"]) if args.llm else n["sentimento_svm"]
        print(f"{n['id']} [{n['estrategia']}] svm={n['sentimento_svm']} final={n['sentimento']} :: {n['titulo'][:60]}")

    SAIDA.write_text(json.dumps(noticias, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nescrito: {SAIDA} ({len(noticias)} notícias)")


if __name__ == "__main__":
    main()
