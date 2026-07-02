import json

import audit


def test_registrar_e_ler(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "consultas.jsonl")
    audit.registrar(rota="/perguntar", fundo="ALFA-33", pergunta="teste?",
                    backend="mock", latency_ms=12,
                    fontes=["01_metodologia_atribuicao.md"], bloqueados=[],
                    resposta="uma resposta qualquer")
    regs = audit.ler(limit=10)
    assert len(regs) == 1
    r = regs[0]
    assert r["rota"] == "/perguntar" and r["fundo"] == "ALFA-33"
    assert r["resposta_hash"] and "resposta" not in r
    assert r["timestamp"]


def test_ler_ordem_e_limite(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "c.jsonl")
    for i in range(5):
        audit.registrar(rota="/narrativa", fundo="ALFA-33", pergunta=f"p{i}",
                        backend="mock", latency_ms=i, fontes=[], bloqueados=[],
                        resposta=str(i))
    regs = audit.ler(limit=3)
    assert [r["pergunta"] for r in regs] == ["p4", "p3", "p2"]


def test_falha_de_escrita_nao_levanta(monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_PATH", audit.Path("/caminho/impossivel/x.jsonl"))
    audit.registrar(rota="/x", fundo="", pergunta="", backend="", latency_ms=0,
                    fontes=[], bloqueados=[], resposta="")  # não deve explodir


def test_ler_sem_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "nao_existe.jsonl")
    assert audit.ler() == []
