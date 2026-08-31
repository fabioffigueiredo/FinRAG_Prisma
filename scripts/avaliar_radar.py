#!/usr/bin/env python3
"""Gate de promoção do classificador do Radar.

O arquivo de avaliação não acompanha manchetes reais pré-rotuladas no
repositório. Ele deve ser preenchido e revisado por duas pessoas antes de
habilitar PRISMA_RADAR_SENTIMENT_ENABLED em qualquer ambiente público.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "prisma-api"))

from radar_pipeline import LocalFinbertClassifier  # noqa: E402

LABELS = ("positivo", "negativo", "neutro")
REQUIRED_FIELDS = {"titulo", "idioma", "sentimento", "revisado_por", "revisado_em"}


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        row = json.loads(raw)
        missing = REQUIRED_FIELDS - row.keys()
        if missing:
            raise ValueError(f"linha {line_no}: faltam campos {sorted(missing)}")
        if row["idioma"] not in {"pt", "en"}:
            raise ValueError(f"linha {line_no}: idioma deve ser pt ou en")
        if row["sentimento"] not in LABELS:
            raise ValueError(f"linha {line_no}: sentimento inválido")
        if not row["revisado_por"] or not row["revisado_em"]:
            raise ValueError(f"linha {line_no}: revisão humana ausente")
        rows.append(row)
    return rows


def macro_f1(expected: list[str], predicted: list[str]) -> float:
    scores = []
    for label in LABELS:
        tp = sum(a == b == label for a, b in zip(expected, predicted))
        fp = sum(a != label and b == label for a, b in zip(expected, predicted))
        fn = sum(a == label and b != label for a, b in zip(expected, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path, help="JSONL revisado manualmente")
    parser.add_argument("--baseline", type=Path, help="JSON com macro_f1 do FinNLP atual")
    args = parser.parse_args()
    rows = load_rows(args.dataset)
    languages = Counter(row["idioma"] for row in rows)
    if len(rows) < 100 or languages["pt"] < 50 or languages["en"] < 50:
        print(json.dumps({"pass": False, "motivo": "exige ao menos 100 manchetes revisadas, 50 PT e 50 EN", "total": len(rows), "idiomas": languages}, ensure_ascii=False))
        return 2

    model = LocalFinbertClassifier()
    expected = [row["sentimento"] for row in rows]
    predicted = [model.classify(row["titulo"])[0] for row in rows]
    result = {"total": len(rows), "macro_f1": round(macro_f1(expected, predicted), 4), "idiomas": languages}
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        baseline_score = float(baseline["macro_f1"])
        result["baseline_macro_f1"] = baseline_score
        result["supera_baseline"] = result["macro_f1"] > baseline_score
        if not result["supera_baseline"]:
            result["pass"] = False
            print(json.dumps(result, ensure_ascii=False))
            return 3
    result["pass"] = True
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
