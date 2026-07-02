"""Carregamento de documentos e chunking consciente.

Decidi quebrar por parágrafo (e por sentença quando o parágrafo é grande)
com sobreposição porque notei, no relato do professor sobre o NotebookLM, que
cortar texto no meio de uma linha gera alucinação na recuperação.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Document:
    id: str
    text: str
    source: str


@dataclass
class Chunk:
    doc_id: str
    chunk_id: int
    text: str
    source: str


def load_documents(folder: "str | Path") -> list[Document]:
    """Leio todos os .txt da pasta; o id é o nome do arquivo sem extensão."""
    folder = Path(folder)
    docs: list[Document] = []
    for path in sorted(folder.glob("*.txt")):
        docs.append(Document(id=path.stem,
                             text=path.read_text(encoding="utf-8"),
                             source=path.name))
    return docs


def _split_units(text: str, max_chars: int = 800) -> list[str]:
    """Divido em parágrafos; parágrafo maior que max_chars vira sentenças."""
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            units.append(para)
        else:
            units.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip())
    return units


def chunk_document(doc: Document, max_chars: int = 800,
                   overlap: int = 150) -> list[Chunk]:
    """Agrupo unidades lógicas até max_chars, com sobreposição de overlap chars."""
    units = _split_units(doc.text, max_chars)
    if not units:
        return []
    chunks: list[str] = []
    current = ""
    for unit in units:
        if current and len(current) + len(unit) + 1 > max_chars:
            chunks.append(current.strip())
            tail = current[-overlap:] if overlap else ""
            if tail:
                space = tail.find(" ")
                # Decidi avançar até o primeiro espaço porque notei que cortar o
                # overlap no meio de uma palavra reintroduz o "chunking cego".
                tail = tail[space + 1:] if space != -1 else tail
            current = (tail + " " + unit).strip() if tail else unit
        else:
            current = (current + " " + unit).strip() if current else unit
    if current.strip():
        chunks.append(current.strip())
    return [Chunk(doc_id=doc.id, chunk_id=i, text=t, source=doc.source)
            for i, t in enumerate(chunks)]


def chunk_corpus(docs: list[Document], max_chars: int = 800,
                 overlap: int = 150) -> list[Chunk]:
    """Aplico o chunking a todo o corpus."""
    out: list[Chunk] = []
    for doc in docs:
        out.extend(chunk_document(doc, max_chars=max_chars, overlap=overlap))
    return out
