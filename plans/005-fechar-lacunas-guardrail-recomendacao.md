# Plan 005: Fechar lacunas de fraseado no guardrail de recomendação (escopo.py)

> **Executor instructions**: Siga este plano passo a passo. Rode cada comando
> de verificação e confirme o resultado esperado antes do próximo passo. Se
> algo na seção "STOP conditions" ocorrer, pare e reporte — não improvise.
> Ao terminar, atualize a linha de status deste plano em `plans/README.md`
> (a menos que quem te despachou tenha dito que cuida do índice).
>
> **Drift check (rode primeiro)**: `git diff --stat d0cb607..HEAD -- services/prisma-api/escopo.py services/prisma-api/tests/test_escopo.py`
> Se `escopo.py` já mudou desde que este plano foi escrito, compare os
> trechos de "Estado atual" abaixo com o código ao vivo antes de prosseguir;
> em caso de divergência, trate como condição de STOP.

## Status

- **Priority**: P0 (guardrail de conformidade regulatória — CVM 20 — com
  lacunas reais confirmadas, não hipotéticas)
- **Effort**: S
- **Risk**: LOW-MED (regex editada com cuidado é aditiva; o risco real é
  falso positivo — bloquear pergunta explicativa legítima — coberto pelo
  Passo 2)
- **Depends on**: none (mas plans/004-catalogo-cenarios-gestor-copiloto.md
  está BLOQUEADO por este achado — depois deste plano, o teste
  `test_pedido_de_recomendacao_e_sempre_recusado` de lá deve passar sem
  alteração)
- **Category**: bug + security (guardrail de compliance)
- **Planned at**: commit `5116bfd`, 2026-07-20

## Por que isso importa

Ao executar `plans/004-catalogo-cenarios-gestor-copiloto.md` (Passo 5,
categoria "pedido de recomendação"), o teste
`test_pedido_de_recomendacao_e_sempre_recusado` falhou na frase **"vale a
pena resgatar agora?"** — uma pergunta claramente pedindo orientação de
resgate, que deveria ser recusada pelo guardrail `escopo.py::pede_recomendacao`
(base: Resolução CVM 20, "explica, não recomenda" — ver
`docs/GOVERNANCA_IA.md` §1), mas passa direto.

Investigação nesta sessão (não é conclusão do executor do plano 004 — ele só
reportou a primeira falha; o teste dele usa `assert` num loop, que para na
primeira frase que falhar, mascarando as demais) confirmou, rodando
`escopo.pede_recomendacao` diretamente pra cada frase, que a lacuna é maior
que uma frase isolada:

```
True   'devo comprar mais cotas desse fundo?'
False  'vale a pena resgatar agora?'
True   'vale a pena investir nesse fundo?'
False  'qual o melhor fundo pra investir esse mês?'   <- também falha!
False  'compensa resgatar agora?'
False  'é bom momento pra sair do fundo?'
True   'devo vender minhas cotas?'
False  'o que eu compro agora?'
```

A pergunta **"qual o melhor fundo pra investir esse mês?"** é uma das 3
frases literais já escritas no PRÓPRIO plano 004 (Passo 5) como exemplo que
deveria ser recusado — e também falha, silenciosamente, porque o teste do
plano 004 usa um loop com `assert` simples (para no primeiro erro). Ou seja:
o guardrail tem pelo menos duas lacunas reais nesse conjunto de frases, não
uma.

Padrão dos gaps encontrados:
1. **Contração coloquial "pra" não é reconhecida** — só "para" está na
   regex (`melhor ... para`). Português falado usa "pra" o tempo todo (o
   próprio vídeo de teste manual desta sessão, transcrito, está cheio de
   "pra").
2. **Lista de verbos incompleta em "vale a pena"** — cobre
   investir/comprar/aplicar, mas não resgatar/sair/vender.
3. **"compensa" como abertura equivalente a "vale a pena" não existe.**
4. **"bom momento para/pra [ação]" não tem padrão nenhum.**
5. **Verbo conjugado ("compro", "vendo") não é reconhecido** — só a forma
   infinitiva ("comprar", "vender").

Isso é uma lacuna de conformidade concreta: um gestor perguntando de forma
natural e coloquial (exatamente como fez no teste manual gravado que deu
origem a esta sessão) tem uma chance real de contornar sem querer um
guardrail que existe especificamente para impedir o Prisma de emitir
recomendação de investimento (Resolução CVM 20).

## Estado atual

`services/prisma-api/escopo.py` completo (não muda fora do bloco `_PADROES`
citado abaixo):

```python
"""Guardrail de escopo: o Prisma explica resultados; não recomenda nem prevê."""
import re

_PADROES = [
    r"devo\s+(comprar|vender|investir|aplicar|resgatar)",
    r"recomend",
    r"previs[aã]o",
    r"vai\s+(subir|cair|render)",
    r"melhor\s+(fundo|investimento|aplica[cç][aã]o)\s+para",
    r"o\s+que\s+(comprar|vender)",
    r"vale\s+a\s+pena\s+(investir|comprar|aplicar)",
]
_RX = re.compile("|".join(_PADROES), re.IGNORECASE)

INSTRUCAO_ESCOPO = (
    "\n\nImportante: você explica resultados passados com base no contexto. "
    "Não faça recomendação de compra/venda nem previsão de mercado."
)

RESPOSTA_ESCOPO = (
    "Posso explicar de onde veio o resultado do fundo e o que os números "
    "significam, mas não faço recomendação de investimento nem previsão de "
    "mercado — o Prisma é explicativo por design. Reformule perguntando sobre "
    "o desempenho observado (ex.: \"de onde veio o retorno no período?\")."
)


def pede_recomendacao(texto: str) -> bool:
    return bool(_RX.search(texto or ""))


# (bloco de tenta_injecao abaixo, não faz parte do escopo deste plano)
```

`services/prisma-api/tests/test_escopo.py` completo hoje (padrão a seguir e
estender, não substituir):

```python
from escopo import pede_recomendacao, INSTRUCAO_ESCOPO, RESPOSTA_ESCOPO


def test_detecta_pedidos_de_recomendacao():
    positivos = [
        "Qual fundo devo comprar?",
        "Você recomenda investir no Alfa?",
        "Qual a previsão para o próximo trimestre?",
        "O Beta vai subir?",
        "Qual o melhor fundo para investir agora?",
    ]
    for p in positivos:
        assert pede_recomendacao(p), p


def test_nao_flagra_perguntas_explicativas():
    negativos = [
        "De onde veio o retorno do fundo no período?",
        "Por que o varejo pesou no resultado?",
        "Compare o Alfa e o Beta no trimestre",
        "O que significa o beta baixo?",
    ]
    for n in negativos:
        assert not pede_recomendacao(n), n


def test_constantes_existem():
    assert "não" in RESPOSTA_ESCOPO.lower()
    assert "recomendação" in INSTRUCAO_ESCOPO.lower() or "recomenda" in INSTRUCAO_ESCOPO.lower()
```

Consumidores de `pede_recomendacao` (não mudam, só pra contexto — não
precisa tocar): `services/prisma-api/app.py`, chamado tanto em `/perguntar`
quanto em `/analisar`, sempre como guard determinístico ANTES de qualquer
chamada a LLM.

## Comandos que você vai precisar

| Propósito | Comando | Esperado no sucesso |
|---|---|---|
| Teste do arquivo alvo | `cd services/prisma-api && source .venv/bin/activate && python -m pytest tests/test_escopo.py -q` | todos passam |
| Suíte completa | `cd services/prisma-api && source .venv/bin/activate && python -m pytest -q` | todos passam, sem regressão |

(Ative o `.venv` que já existe nesta worktree, ou crie um novo com
`python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
se estiver numa worktree fresca.)

## Escopo

**Dentro do escopo**:
- `services/prisma-api/escopo.py` (só a lista `_PADROES`)
- `services/prisma-api/tests/test_escopo.py` (estender)

**Fora do escopo**:
- `_PADROES_INJECAO`/`tenta_injecao` no mesmo arquivo — não mude, não é
  parte deste achado.
- `app.py`, `agent.py` — nenhum consumidor de `pede_recomendacao` precisa
  mudar; a função continua com a mesma assinatura e contrato (`str -> bool`).
- `plans/004-catalogo-cenarios-gestor-copiloto.md` — não edite esse plano;
  depois deste fix, o teste dele deve passar tal como está escrito.

## Git workflow

- Branch: `advisor/005-guardrail-recomendacao`.
- Um commit; Conventional Commits (ex.: `fix(escopo): cobre fraseado
  coloquial no guardrail de recomendação — CVM 20`).
- NÃO dê push nem abra PR a menos que instruído.

## Passos

### Passo 1 — Estender `_PADROES` pra cobrir os gaps confirmados

Em `services/prisma-api/escopo.py`, troque a lista `_PADROES` por:

```python
_PADROES = [
    r"devo\s+(comprar|vender|investir|aplicar|resgatar|sair|entrar)",
    r"recomend",
    r"previs[aã]o",
    r"vai\s+(subir|cair|render)",
    r"melhor\s+(fundo|investimento|aplica[cç][aã]o)\s+(para|pra)",
    r"o\s+que\s+(eu\s+)?(compr(ar|o|a)|vend(er|o|e))",
    r"(vale\s+a\s+pena|compensa)\s+(investir|comprar|aplicar|resgatar|sair|vender)",
    r"bom\s+momento\s+(para|pra)\s+(comprar|vender|resgatar|sair|entrar)",
]
```

Mudanças em relação ao original, cada uma resolvendo um gap específico
listado em "Por que isso importa":
1. `devo\s+(...)` ganhou `sair|entrar` — cobre "devo sair do fundo?"/"devo
   entrar agora?", mesma família semântica de resgatar/investir.
2. `melhor\s+(...)` ganhou `|pra` ao lado de `para` — resolve o gap #1.
3. `o\s+que\s+(...)` ganhou `(eu\s+)?` opcional e formas conjugadas
   `compr(ar|o|a)`/`vend(er|o|e)` — resolve o gap #5 ("o que eu compro
   agora?", "o que vende mais rápido?" continua coberto pela forma
   original).
4. `vale a pena` virou `(vale\s+a\s+pena|compensa)` com a lista de verbos
   ampliada pra `investir|comprar|aplicar|resgatar|sair|vender` — resolve
   os gaps #2 e #3.
5. Novo padrão `bom\s+momento\s+(...)` — resolve o gap #4.

**Verificar**: `python -c "
import escopo
casos = ['vale a pena resgatar agora?', 'qual o melhor fundo pra investir esse mês?',
         'compensa resgatar agora?', 'é bom momento pra sair do fundo?', 'o que eu compro agora?']
for c in casos:
    assert escopo.pede_recomendacao(c), f'ainda nao cobre: {c!r}'
print('OK: todos os 5 casos do achado agora são recusados')
"` → imprime a mensagem OK sem `AssertionError`.

### Passo 2 — Confirmar que nenhuma pergunta explicativa legítima passou a ser bloqueada (falso positivo)

Este é o passo que mais importa neste plano — ampliar demais a regex pode
bloquear perguntas legítimas de um gestor, o que seria pior que a lacuna
original (o copiloto ficaria inútil pra perguntas normais). Rode o teste
negativo já existente MAIS uma lista adicional de perguntas explicativas
plausíveis que tocam em palavras próximas das novas ("sair", "entrar",
"melhor", "momento") mas SEM pedir recomendação:

```python
python -c "
import escopo
negativos_novos = [
    'Por que o fundo saiu da faixa de volatilidade esperada?',
    'Quando o gestor entrou nessa posição?',
    'Qual foi o melhor mês do fundo em 2026?',
    'Em que momento do trimestre o retorno virou positivo?',
    'Quanto o fundo vendeu em cotas de Bolsa Brasil no período?',
]
for n in negativos_novos:
    assert not escopo.pede_recomendacao(n), f'FALSO POSITIVO: {n!r}'
print('OK: nenhum falso positivo nas perguntas explicativas testadas')
"
```

**Verificar**: imprime `OK`, sem `AssertionError`. **Se qualquer uma
disparar falso positivo, NÃO force a regex a passar removendo a
generalidade do Passo 1** — em vez disso, torne o padrão específico o
suficiente pra não pegar essas frases (ex.: exigir a palavra logo adjacente
ao verbo em vez de em qualquer lugar da frase) e rode este passo de novo
antes de prosseguir. Se não conseguir resolver sem reintroduzir algum gap do
Passo 1, pare e reporte (ver STOP conditions) — não é pra escolher
silenciosamente entre "menos falso positivo" e "menos falso negativo" sem
reportar o trade-off pro revisor.

### Passo 3 — Formalizar os dois testes em `test_escopo.py`

Adicione ao arquivo, seguindo o padrão de lista+loop já usado (mas cobrindo
TODAS as frases, sem parar na primeira falha — é exatamente o que escondeu
o segundo gap no plano 004; use um loop que coleta todas as falhas antes de
assertar, não um `assert` direto dentro do `for`):

```python
def test_cobre_fraseado_coloquial_de_recomendacao():
    """Achado de plans/005-fechar-lacunas-guardrail-recomendacao.md — cada
    frase aqui falhava antes deste plano. Loop coleta TODAS as falhas antes
    de assertar (não para na primeira), pra nunca mais esconder um segundo
    gap como aconteceu na execução do plano 004."""
    positivos = [
        "vale a pena resgatar agora?",
        "qual o melhor fundo pra investir esse mês?",
        "compensa resgatar agora?",
        "é bom momento pra sair do fundo?",
        "o que eu compro agora?",
        "devo sair desse fundo?",
    ]
    falhas = [p for p in positivos if not pede_recomendacao(p)]
    assert not falhas, f"não recusadas: {falhas}"


def test_nao_flagra_explicativas_proximas_do_novo_vocabulario():
    """Perguntas legítimas que usam palavras parecidas com as novas do
    guardrail (sair/entrar/melhor/momento) mas não pedem recomendação."""
    negativos = [
        "Por que o fundo saiu da faixa de volatilidade esperada?",
        "Quando o gestor entrou nessa posição?",
        "Qual foi o melhor mês do fundo em 2026?",
        "Em que momento do trimestre o retorno virou positivo?",
        "Quanto o fundo vendeu em cotas de Bolsa Brasil no período?",
    ]
    falhas = [n for n in negativos if pede_recomendacao(n)]
    assert not falhas, f"falsos positivos: {falhas}"
```

**Verificar**: `python -m pytest tests/test_escopo.py -v` → todos passam,
incluindo os 2 novos e os 3 já existentes (5 no total).

### Passo 4 — Confirmar que o plano 004 destrava

Se você tiver acesso ao arquivo `services/prisma-api/tests/test_copiloto_cenarios_gestor.py`
(criado — mas não commitado — pela execução anterior do plano 004 nesta
mesma worktree, ou copie o Passo 5 dele se não estiver presente):

```python
python -m pytest tests/test_copiloto_cenarios_gestor.py::test_pedido_de_recomendacao_e_sempre_recusado -q
```

**Verificar**: passa. Se o arquivo não existir nesta worktree, pule este
passo — não é obrigatório criar o arquivo do plano 004 aqui, só confirmar
via `escopo.pede_recomendacao` direto (Passo 1) que a causa raiz foi
resolvida.

## Plano de testes

Já detalhado nos Passos 2 e 3 acima — são o entregável principal deste
plano. Resumo: 2 funções novas em `test_escopo.py`
(`test_cobre_fraseado_coloquial_de_recomendacao`,
`test_nao_flagra_explicativas_proximas_do_novo_vocabulario`), cobrindo 6
casos positivos (recusa) e 5 casos negativos (não-recusa/explicativo).

Verificação final: `cd services/prisma-api && source .venv/bin/activate && python -m pytest -q` → todos passam, incluindo os novos, sem regressão na suíte completa.

## Critérios de conclusão

- [ ] `python -m pytest tests/test_escopo.py -v` → 5 testes, todos passam (3 originais + 2 novos)
- [ ] Os 5 casos positivos listados em "Por que isso importa" retornam `True` em `pede_recomendacao`
- [ ] Os 5 casos negativos do Passo 2 continuam retornando `False`
- [ ] `python -m pytest services/prisma-api -q` → sem regressão na suíte completa
- [ ] Nenhum arquivo fora de `escopo.py`/`tests/test_escopo.py` foi modificado (`git status`)
- [ ] `plans/README.md` — SKIP se dispatchado via `execute` (reviewer cuida)

## STOP conditions

Pare e reporte (não improvise) se:

- Qualquer caso do Passo 2 (falso positivo) continuar falhando depois de
  ajustar a regex uma vez — não fique tentando várias rodadas de regex até
  acertar às cegas; pare e apresente o trade-off encontrado.
- `pede_recomendacao` for chamada em algum lugar do código com uma
  assinatura diferente de `(texto: str) -> bool` (mudança de contrato) —
  isso quebraria os chamadores em `app.py`; pare, não mude o contrato.
- Os testes de `test_escopo.py` já cobrirem algum dos casos deste plano
  (alguém já corrigiu isso) — compare e não duplique; se já estiver
  corrigido, marque este plano como REJECTED/já resolvido no índice.

## Notas de manutenção

- Este guardrail é baseado em regex determinística de propósito (não LLM) —
  rápido e auditável, mas por natureza vai sempre ter uma cauda de
  fraseados não cobertos. Não existe uma correção "completa"; o padrão
  certo é: quando aparecer um novo fraseado que escapa (via teste manual,
  relatório de usuário, ou auditoria dos logs de `/analisar`/`/perguntar`
  que tiveram `escopo: false` mas continham linguagem de decisão), ele
  entra como um novo caso no `test_cobre_fraseado_coloquial_de_recomendacao`
  antes de editar a regex — mesmo ciclo deste plano.
- Depois deste plano, retome `plans/004-catalogo-cenarios-gestor-copiloto.md`
  a partir de onde parou (Categoria D também tinha uma falha reportada,
  separada — "fundo inexistente cai silenciosamente no fundo em foco da
  tela em vez de avisar" — não é STOP condition do plano 004, mas fica
  registrado pro revisor decidir se vira achado novo ou ajuste de teste).
