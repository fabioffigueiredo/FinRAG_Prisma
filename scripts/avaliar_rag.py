"""Avaliação de recuperação (Precision@k / Hit@k) do RAG do Prisma.

Conjunto de golden queries: pergunta -> fonte esperada no top-k. Roda contra a
API no ar (localhost:8000). Publica a tabela no README (docs/METRICAS_RAG.md).

Uso: python scripts/avaliar_rag.py
"""
from __future__ import annotations

import json
import urllib.request

API = "http://localhost:8000/perguntar"
K = 4

GOLDEN = [
    ("O que significa alpha e beta?", "03_glossario_benchmark"),
    ("Como é calculada a contribuição de cada ativo?", "01_metodologia_atribuicao"),
    ("O que é a estratégia de crédito privado?", "02_taxonomia_estrategias"),
    ("Por que o varejo pesou no resultado?", "noticia:n07"),
    ("Como o setor bancário contribuiu?", "noticia:n05"),
    ("O que aconteceu com o câmbio no período?", "noticia:n08"),
    ("Qual foi o retorno do fundo Alfa?", "dados:ALFA-33"),
    ("Como funciona o benchmark do fundo?", "03_glossario_benchmark"),
]


def _fontes(pergunta: str) -> list[str]:
    body = json.dumps({"pergunta": pergunta, "backend": "mock", "fundo": "ALFA-33"}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    return [c["fonte"] for c in d.get("citacoes", [])]


def main() -> None:
    hits, linhas = 0, []
    for pergunta, esperado in GOLDEN:
        fontes = _fontes(pergunta)
        pos = next((i + 1 for i, f in enumerate(fontes[:K]) if esperado in f), None)
        ok = pos is not None
        hits += ok
        linhas.append((pergunta, esperado, pos, ok))
        print(f"[{'OK ' if ok else 'X  '}] top{pos or '-'}  {esperado:28} :: {pergunta}")

    hit_at_k = hits / len(GOLDEN)
    mrr = sum(1 / p for *_, p, ok in [(l[0], l[1], l[2], l[3]) for l in linhas] if ok and p) / len(GOLDEN)
    print(f"\nHit@{K} = {hit_at_k:.0%} · MRR = {mrr:.2f}")

    md = ["# Métricas de recuperação (RAG)", "",
          f"Conjunto de {len(GOLDEN)} *golden queries* do domínio; fonte esperada no top-{K}.",
          f"Reproduza com `python scripts/avaliar_rag.py` (API no ar).", "",
          f"**Hit@{K} = {hit_at_k:.0%}** · **MRR = {mrr:.2f}**", "",
          "| Pergunta | Fonte esperada | Posição |", "|---|---|:--:|"]
    for pergunta, esperado, pos, ok in linhas:
        md.append(f"| {pergunta} | `{esperado}` | {'top-'+str(pos) if ok else '—'} |")
    md += ["", "> Recuperação com embeddings `bge-m3` (1024-d) sobre regras de "
           "atribuição + notícias classificadas + dados do fundo. Guardrail de "
           "injeção e de escopo aplicados após a recuperação."]
    import pathlib
    pathlib.Path("docs/METRICAS_RAG.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("escrito: docs/METRICAS_RAG.md")


if __name__ == "__main__":
    main()
