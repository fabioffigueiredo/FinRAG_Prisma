"""Repositório de acesso a dado (Meta 1).

`popular_do_conector` traduz qualquer `FundoConnector`+`EstrategiaConnector`+
`VarConnector`+`BenchmarkConnector` (hoje o `SimuladorConnector`, amanhã um
conector real) pro schema Postgres. `aplicar_classificacao_estrategia` é a
função mais crítica do módulo — é o SCD2 de verdade: fecha a versão vigente
anterior e abre uma nova, com hash de auditoria, tudo numa transação.
"""
from __future__ import annotations

import difflib
import hashlib
import json
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestao.base import ConectorCompleto

from .models import (
    Ativo,
    Benchmark,
    BenchmarkPeso,
    Contribuicao,
    Dimensao,
    EstrategiaVersao,
    Fundo,
    LogAlteracaoEstrategia,
    Periodo,
    SerieDiaria,
    VarClasseDiaria,
)


DIMENSOES = [
    "estrategia", "grupo_contabil", "supergrupo", "privados",
    "renda_variavel", "renda_fixa", "vencimento", "ativos",
]


def _hash_classificacao(fundo_codigo: str, ativo_codigo: str, nome_estrategia: str,
                        matricula: str, criado_em: datetime) -> str:
    """Hash determinístico do evento de classificação — mesmo princípio do
    `generate_payload_hash` do sistema real (SHA-256 sobre o payload
    canônico), mas sem nenhum campo de texto livre na composição da CHAVE
    (o hash em si pode incluir o nome só como metadado de auditoria)."""
    payload = f"{fundo_codigo}|{ativo_codigo}|{nome_estrategia}|{matricula}|{criado_em.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalizar_nome(nome: str) -> str:
    return " ".join(nome.strip().lower().split())


def detectar_near_duplicates_ativo(db: Session, ativo_nome: str, *,
                                   excluir_codigo: str | None = None,
                                   limiar: float = 0.82) -> list[dict]:
    """Antes de cadastrar um ativo NOVO (código ainda não existe), avisa se
    o nome é PARECIDO com um ativo já cadastrado — é a mesma armadilha do
    `NOME_LONGO_TITULO` texto-livre do sistema real: um erro de digitação
    ("Debenture" sem acento, por exemplo) cria um ativo duplicado em vez de
    reaproveitar o existente, e ninguém percebe até o batimento divergir.

    Decidi usar `difflib` (stdlib, sem dependência nova) em vez de um
    embedding — pra esse caso (nomes curtos, erro de digitação/acentuação)
    a distância de string já resolve bem e é auditável (não é uma caixa-preta).
    """
    alvo = _normalizar_nome(ativo_nome)
    achados = []
    for candidato in db.scalars(select(Ativo)):
        if excluir_codigo and candidato.codigo == excluir_codigo:
            continue
        score = difflib.SequenceMatcher(None, alvo, _normalizar_nome(candidato.nome)).ratio()
        if score >= limiar:
            achados.append({"ativo_codigo": candidato.codigo, "ativo_nome": candidato.nome,
                            "similaridade": round(score, 3)})
    achados.sort(key=lambda a: -a["similaridade"])
    return achados


def _obter_ou_criar_ativo(db: Session, codigo: str, nome: str, tipo: str) -> Ativo:
    ativo = db.scalar(select(Ativo).where(Ativo.codigo == codigo))
    if ativo is None:
        ativo = Ativo(codigo=codigo, nome=nome, tipo=tipo)
        db.add(ativo)
        db.flush()
    return ativo


def aplicar_classificacao_estrategia(
    db: Session, *, fundo_codigo: str, ativo_codigo: str, ativo_nome: str,
    ativo_tipo: str, nome_estrategia: str, matricula: str,
    hoje: date | None = None,
) -> LogAlteracaoEstrategia:
    """SCD2: fecha a versão vigente anterior (se houver) e abre uma nova.

    A chave natural é (fundo_codigo, ativo_id) — nunca texto livre. Se a
    estratégia pedida for igual à vigente, ainda assim registra o evento no
    log (idempotência de dado não é a mesma coisa que idempotência de
    auditoria: cada import é um evento).
    """
    hoje = hoje or date.today()
    ativo = _obter_ou_criar_ativo(db, ativo_codigo, ativo_nome, ativo_tipo)

    vigente = db.scalar(
        select(EstrategiaVersao).where(
            EstrategiaVersao.fundo_codigo == fundo_codigo,
            EstrategiaVersao.ativo_id == ativo.id,
            EstrategiaVersao.vigente.is_(True),
        )
    )
    if vigente is not None:
        vigente.vigente = False
        vigente.dt_fim_vigencia = hoje

    nova = EstrategiaVersao(
        fundo_codigo=fundo_codigo, ativo_id=ativo.id, nome_estrategia=nome_estrategia,
        dt_inicio_vigencia=hoje, dt_fim_vigencia=None, vigente=True,
        matricula_responsavel=matricula,
    )
    db.add(nova)
    db.flush()  # garante nova.id antes do log/hash

    criado_em = datetime.now(timezone.utc)
    hash_evento = _hash_classificacao(fundo_codigo, ativo_codigo, nome_estrategia, matricula, criado_em)
    log = LogAlteracaoEstrategia(
        estrategia_versao_id=nova.id, hash_sha256=hash_evento, tipo_alteracao="import_csv",
        matricula=matricula,
        payload_json=json.dumps({"fundo": fundo_codigo, "ativo": ativo_codigo,
                                 "estrategia": nome_estrategia}, ensure_ascii=False),
    )
    db.add(log)
    return log


def popular_do_conector(
    db: Session,
    conector: ConectorCompleto,
    matricula: str = "SIMULADOR",
) -> None:
    """Popula o Postgres inteiro a partir de um conector (hoje o
    `SimuladorConnector`). Idempotente o bastante pra rodar em cima de um
    banco vazio (não faz upsert de período/fundo já existente)."""
    for fundo_dto in conector.listar_fundos():
        fundo = db.get(Fundo, fundo_dto.codigo) or Fundo(codigo=fundo_dto.codigo)
        fundo.nome = fundo_dto.nome
        fundo.cnpj = fundo_dto.cnpj
        fundo.classe = fundo_dto.classe
        fundo.benchmark_padrao = fundo_dto.benchmark_padrao
        db.add(fundo)
        db.flush()

        periodos_db: dict[str, Periodo] = {}
        for periodo_dto in conector.obter_periodos(fundo_dto.codigo):
            periodo = Periodo(fundo_codigo=fundo.codigo, label=periodo_dto.label,
                             data_inicio=periodo_dto.data_inicio, data_fim=periodo_dto.data_fim)
            db.add(periodo)
            db.flush()
            periodos_db[periodo_dto.label] = periodo

            for ponto in conector.obter_serie_diaria(fundo.codigo, periodo_dto.label):
                db.add(SerieDiaria(fundo_codigo=fundo.codigo, periodo_id=periodo.id,
                                   data=ponto.data, cota=ponto.cota, bench=ponto.bench))

            for dimensao in DIMENSOES:
                for c in conector.obter_contribuicoes(fundo.codigo, periodo_dto.label, dimensao):
                    db.add(Contribuicao(fundo_codigo=fundo.codigo, periodo_id=periodo.id,
                                        dimensao=dimensao, chave_dimensao=c.chave_dimensao,
                                        contribuicao_pp=c.contribuicao_pp, peso_medio=c.peso_medio,
                                        cor=c.cor))

            for var_ponto in conector.obter_var(fundo.codigo, periodo_dto.data_inicio, periodo_dto.data_fim):
                db.add(VarClasseDiaria(fundo_codigo=fundo.codigo, data=var_ponto.data,
                                       classe=var_ponto.classe, valor_pct_nav=var_ponto.valor_pct_nav))

            for peso_dto in conector.obter_pesos(fundo.codigo, periodo_dto.label):
                bench = db.scalar(select(Benchmark).where(Benchmark.nome == peso_dto.benchmark_nome))
                if bench is None:
                    bench = Benchmark(nome=peso_dto.benchmark_nome)
                    db.add(bench)
                    db.flush()
                db.add(BenchmarkPeso(fundo_codigo=fundo.codigo, periodo_id=periodo.id,
                                     benchmark_id=bench.id, peso=peso_dto.peso))

        for classificacao in conector.obter_classificacao_atual(fundo.codigo):
            aplicar_classificacao_estrategia(
                db, fundo_codigo=fundo.codigo, ativo_codigo=classificacao.ativo_codigo,
                ativo_nome=classificacao.ativo_nome, ativo_tipo=classificacao.ativo_tipo,
                nome_estrategia=classificacao.nome_estrategia, matricula=matricula,
            )
    db.commit()


def obter_contribuicoes_dimensao(db: Session, fundo_codigo: str, periodo_label: str,
                                 dimensao: str) -> list[dict]:
    """Lê contribuições de uma dimensão específica do Postgres (Meta 3) —
    é o que liga o copiloto às 7 dimensões que antes só existiam como aviso
    de 'indisponível na demo' em `agent.py::_tool_obter_atribuicao`."""
    try:
        dim = Dimensao(dimensao)
    except ValueError:
        return []
    periodo = db.scalar(
        select(Periodo).where(Periodo.fundo_codigo == fundo_codigo, Periodo.label == periodo_label)
    )
    if periodo is None:
        return []
    linhas = db.scalars(
        select(Contribuicao).where(
            Contribuicao.fundo_codigo == fundo_codigo,
            Contribuicao.periodo_id == periodo.id,
            Contribuicao.dimensao == dim,
        )
    )
    return [
        {"nome": c.chave_dimensao, "contribuicao_pp": c.contribuicao_pp,
         "peso_medio": c.peso_medio, "cor": c.cor}
        for c in linhas
    ]


def obter_periodos_disponiveis(db: Session, fundo_codigo: str) -> list[dict]:
    """Lista os períodos com dado carregado pra um fundo — usado pela
    narrativa proativa (Meta 3) pra achar 'o período anterior'."""
    periodos = db.scalars(
        select(Periodo).where(Periodo.fundo_codigo == fundo_codigo).order_by(Periodo.data_inicio)
    )
    return [{"label": p.label, "data_inicio": p.data_inicio, "data_fim": p.data_fim} for p in periodos]


def comparar_periodos_dimensao(db: Session, fundo_codigo: str, dimensao: str = "estrategia") -> dict | None:
    """Compara o período mais recente com o anterior — quem cresceu, quem
    caiu, por quanto. Devolvo os NÚMEROS já calculados (deltas); quem
    narra é o LLM no `agent.py`, nunca esta função (mesmo princípio de
    'o LLM planeja e narra, nunca calcula' do resto do copiloto)."""
    periodos = obter_periodos_disponiveis(db, fundo_codigo)
    if len(periodos) < 2:
        return None
    atual, anterior = periodos[-1], periodos[-2]

    atuais = {c["nome"]: c["contribuicao_pp"]
             for c in obter_contribuicoes_dimensao(db, fundo_codigo, atual["label"], dimensao)}
    anteriores = {c["nome"]: c["contribuicao_pp"]
                 for c in obter_contribuicoes_dimensao(db, fundo_codigo, anterior["label"], dimensao)}
    if not atuais or not anteriores:
        return None

    buckets = sorted(set(atuais) | set(anteriores))
    deltas = [
        {"chave": b, "contribuicao_atual_pp": round(atuais.get(b, 0.0), 2),
         "contribuicao_anterior_pp": round(anteriores.get(b, 0.0), 2),
         "delta_pp": round(atuais.get(b, 0.0) - anteriores.get(b, 0.0), 2)}
        for b in buckets
    ]
    deltas.sort(key=lambda d: abs(d["delta_pp"]), reverse=True)

    retorno_atual = _ultimo_cota(db, fundo_codigo, atual["label"])
    retorno_anterior = _ultimo_cota(db, fundo_codigo, anterior["label"])

    return {
        "periodo_atual": atual["label"], "periodo_anterior": anterior["label"],
        "dimensao": dimensao,
        "retorno_cota_atual_pp": retorno_atual, "retorno_cota_anterior_pp": retorno_anterior,
        "delta_retorno_cota_pp": (round(retorno_atual - retorno_anterior, 2)
                                 if retorno_atual is not None and retorno_anterior is not None else None),
        "maiores_variacoes": deltas[:5],
    }


def _ultimo_cota(db: Session, fundo_codigo: str, periodo_label: str) -> float | None:
    periodo = db.scalar(
        select(Periodo).where(Periodo.fundo_codigo == fundo_codigo, Periodo.label == periodo_label)
    )
    if periodo is None:
        return None
    ponto = db.scalar(
        select(SerieDiaria).where(
            SerieDiaria.fundo_codigo == fundo_codigo, SerieDiaria.periodo_id == periodo.id,
        ).order_by(SerieDiaria.data.desc()).limit(1)
    )
    return ponto.cota if ponto else None


def listar_fundos_da_gestora(db: Session, gestora_id: int) -> list[Fundo]:
    """Meta 4 — isolamento multi-tenant: só devolve fundos da gestora do
    usuário autenticado. É essa função (não uma checagem espalhada em cada
    rota) que garante que a Gestora A nunca vê os fundos da Gestora B."""
    return list(db.scalars(select(Fundo).where(Fundo.gestora_id == gestora_id).order_by(Fundo.codigo)))
