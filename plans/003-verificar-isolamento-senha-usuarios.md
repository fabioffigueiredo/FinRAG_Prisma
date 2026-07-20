# Plan 003: Provar ou refutar suspeita de contaminação de senha entre usuários (com teste) + lacunas de UX em "Meu Perfil"

> **Executor instructions**: Siga este plano passo a passo. Rode cada comando
> de verificação e confirme o resultado esperado antes do próximo passo. Se
> algo na seção "STOP conditions" ocorrer, pare e reporte — não improvise,
> principalmente no Passo 1 (é investigação de segurança, não é pra
> "consertar às cegas"). Ao terminar, atualize a linha de status deste plano
> em `plans/README.md`.
>
> **Drift check (rode primeiro)**: `git diff --stat d0cb607..HEAD -- services/prisma-api/app.py services/prisma-api/db/repo.py services/prisma-api/auth.py apps/web/src/app/\(app\)/admin/usuarios/page.tsx apps/web/src/app/\(app\)/perfil/page.tsx`
> Se algum desses arquivos mudou desde que este plano foi escrito, compare os
> trechos de "Estado atual" abaixo com o código ao vivo antes de prosseguir;
> em caso de divergência, trate como condição de STOP.
>
> **Aviso sobre a árvore de trabalho**: no momento em que este plano foi
> escrito, `services/prisma-api/app.py`, `auth.py` e `db/models.py` já
> tinham mudanças NÃO commitadas de uma revisão de código anterior (2FA,
> cadastro/convite). Rode `git status` antes de editar; não misture essas
> mudanças alheias no seu commit. Se estiver numa worktree isolada
> (`execute`), isso não te afeta.

## Status

- **Priority**: P0 (Passo 1 — segurança, precisa virar teste antes de
  qualquer outra coisa) / P2 (Passos 2–3 — UX)
- **Effort**: S (Passo 1) + S (Passos 2–3, se o achado se confirmar; senão
  vira só "investigar e reportar")
- **Risk**: LOW no Passo 1 em si (é só teste novo — a menos que o teste
  REVELE um bug real, aí o risco depende do que for encontrado, e a
  correção fica fora deste plano por design, ver STOP conditions)
- **Depends on**: none (independente do plano 002)
- **Category**: security (Passo 1, claim não verificado) + dx/docs (Passos 2–3)
- **Planned at**: commit `d0cb607`, 2026-07-20

## Por que isso importa

Durante o mesmo teste manual do plano 002, o gestor testando o painel de
administração de usuários (`/admin/usuarios`) narrou, ao vivo, uma sequência
confusa de edições — revogar sessão, definir senha nova pra um usuário
"teste", depois editar a própria senha de gestor — e concluiu, em dúvida:
"Parece que quando eu mudo a senha de um, eu mudo a senha de todos" e, mais
adiante, tentando logar de novo com o usuário "teste": "a senha que está
aqui é a antiga... senha não mudou não."

Isso é uma alegação séria (contaminação de credencial entre contas, ou
troca de senha que não persiste) que precisa ser levada a sério NUM AMBIENTE
REGULADO — mas a narração em si é autocontraditória o bastante (o autor
claramente se confundiu sobre qual usuário estava editando em vários pontos)
pra não virar uma conclusão sem reprodução controlada.

Uma primeira leitura de código nesta sessão (não é uma investigação
completa — é o motivo deste plano existir) NÃO encontrou nenhum mecanismo
óbvio de estado compartilhado:

- `atualizar_usuario` (`db/repo.py:320-327`) faz `setattr` numa instância
  SQLAlchemy já buscada por id (`buscar_usuario_por_id(db, usuario_id)`,
  chamada em `app.py::atualizar_usuario_rota`) — isso é escopado por linha,
  não deveria vazar pra outra linha da tabela.
- O modal de edição do frontend (`UsuarioDialog`,
  `apps/web/src/app/(app)/admin/usuarios/page.tsx`) reresenta o `form` via
  `useEffect` com dependências `[aberto, editando]` toda vez que
  `editando` muda — e `abrirEdicao(u)` seta `editando`/`dialogAberto`
  atomicamente com o `u` correto da linha clicada (closure por linha, sem
  estado global intermediário visível).

Ou seja: a hipótese mais provável, a esta altura, é que o usuário se
confundiu sobre QUAL conta estava editando/logando durante um teste manual
rápido com múltiplas trocas de sessão — não um bug de isolamento real. Mas
"provável" não é o mesmo que "provado", e a alegação é grave demais pra ficar
sem teste. Este plano existe pra fechar essa pergunta com uma reprodução
controlada e determinística, e só então decidir se há algo a corrigir.

Separadamente, o mesmo teste apontou duas lacunas de UX (menor prioridade,
não relacionadas à suspeita de segurança):
- Em "Meu Perfil" (`apps/web/src/app/(app)/perfil/page.tsx`), o gestor não
  encontrou um caminho claro pra criar um novo usuário nem uma indicação
  clara do próprio papel (a tela existe, mas a navegação/cópia não deixou
  isso óbvio pra quem estava testando).
- Ao criar um usuário, o papel efetivamente salvo pareceu, num teste manual,
  diferente do que foi pedido no formulário — a leitura de
  `criar_usuario_rota` (`app.py:1061-1086`) não mostra nenhum bug óbvio
  (`Papel(req.papel)` é usado direto, sem transformação), então isso também
  fica marcado como "não reproduzido ainda", não como bug confirmado.

## Estado atual

- `services/prisma-api/db/repo.py:320-327`:
  ```python
  def atualizar_usuario(db: Session, usuario: Usuario, **campos) -> Usuario:
      """Update parcial — só aplica as chaves passadas. `matricula` e
      `gestora_id` são imutáveis por design (a rota nem aceita esses campos no
      payload; ver `app.py::atualizar_usuario_rota`)."""
      for chave, valor in campos.items():
          setattr(usuario, chave, valor)
      db.flush()
      return usuario
  ```
- `services/prisma-api/app.py` — rota `PATCH /usuarios/{usuario_id}`
  (`atualizar_usuario_rota`, por volta da linha 1253): busca `alvo =
  buscar_usuario_por_id(db, usuario_id)`, monta o dict `campos` a partir do
  payload (`req.senha` vira `campos["senha_hash"] = auth.hash_senha(...)`
  quando presente), chama `atualizar_usuario(db, alvo, **campos)`, depois
  `db.commit()`.
- `services/prisma-api/tests/test_usuarios_crud.py` — já tem fixtures e
  padrão HTTP prontos pra reusar:
  ```python
  def _gestora_com_usuario(db, matricula="ADMIN-A", papel=Papel.GESTOR, gestora_nome="Gestora A") -> tuple[Gestora, Usuario]:
      ...  # cria Gestora + Usuario ativo, senha "senha123"

  def _login(client, matricula: str, senha: str = "senha123") -> None: ...
  def _csrf_headers(client) -> dict: ...

  def test_gestor_atualiza_papel_de_usuario_da_propria_gestora(client, db):
      gestora, _ = _gestora_com_usuario(db, matricula="GESTOR-L1", gestora_nome="Gestora L")
      alvo = Usuario(matricula="ANALISTA-L1", nome="Fulano", senha_hash=auth.hash_senha("x"),
                    papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
      db.add(alvo)
      db.flush()
      _login(client, "GESTOR-L1")
      resp = client.patch(f"/usuarios/{alvo.id}", json={"papel": "compliance"}, headers=_csrf_headers(client))
      assert resp.status_code == 200
      assert resp.json()["papel"] == "compliance"
  ```
- `apps/web/src/app/(app)/admin/usuarios/page.tsx` (linhas ~570-596):
  ```tsx
  const [dialogAberto, setDialogAberto] = useState(false);
  const [editando, setEditando] = useState<Usuario | null>(null);

  function abrirEdicao(u: Usuario) {
    setEditando(u);
    setDialogAberto(true);
  }
  ```
  e (linhas ~287-311) o `UsuarioDialog` reseta `form` num `useEffect` com
  deps `[aberto, editando]`.
- `services/prisma-api/app.py:1061-1086` (`criar_usuario_rota`): usa
  `Papel(req.papel)` direto do payload, sem transformação — ver "Estado
  atual" completo já citado acima em "Por que isso importa".
- `apps/web/src/app/(app)/perfil/page.tsx:82`:
  `if (!usuario || (usuario.papel !== "gestor" && usuario.papel !==
  "compliance")) return null;` — guarda de uma seção específica da tela
  (a leitura desta sessão não foi funda o bastante pra saber qual; o Passo 3
  pede investigação fresca).

## Comandos que você vai precisar

| Propósito | Comando | Esperado no sucesso |
|---|---|---|
| Postgres de dev (se não estiver rodando) | `docker ps --format "{{.Names}}" \| grep prisma-db \|\| (cd /Users/fabiofigueiredo/Projetos/prisma && docker compose -f docker-compose.dev.yml up -d)` | container `Up` |
| Testes do arquivo alvo | `cd services/prisma-api && source ../../.venv/bin/activate && python -m pytest tests/test_usuarios_crud.py -q` | todos passam |
| Suíte completa | `cd services/prisma-api && source ../../.venv/bin/activate && python -m pytest -q` | todos passam (baseline: 195 passed, 5 skipped) |

## Escopo

**Dentro do escopo**:
- `services/prisma-api/tests/test_usuarios_crud.py` (adicionar testes —
  Passo 1)
- `apps/web/src/app/(app)/perfil/page.tsx` (só se o Passo 3 confirmar um
  achado concreto e pequeno o bastante pra corrigir dentro deste plano —
  ver critério explícito no Passo 3)
- Qualquer arquivo que o Passo 1 apontar como causa raiz de um bug real —
  MAS ver STOP conditions: a correção em si, se o escopo for maior que
  trivial, deve virar um plano novo (004), não ser encaixada aqui.

**Fora do escopo**:
- Qualquer mudança em `services/prisma-api/agent.py`, `llm.py`,
  `sinais.py` — pertence ao plano 002.
- `admin/usuarios/page.tsx` além do que for estritamente necessário se o
  Passo 1 confirmar um bug de frontend — não refatore o arquivo por conta
  própria.
- Qualquer coisa em `app.py`/`auth.py`/`db/models.py` relacionada a
  2FA/cadastro/convite (mudanças de outra frente já em andamento na árvore
  de trabalho — ver aviso no topo).

## Git workflow

- Branch: `advisor/003-isolamento-senha-usuarios`.
- Commit por passo; Conventional Commits (ver `git log --oneline -10`).
- NÃO dê push nem abra PR a menos que instruído.

## Passos

### Passo 1 — Reproduzir (ou refutar) a contaminação de senha entre usuários (P0)

Em `services/prisma-api/tests/test_usuarios_crud.py`, adicione um teste que
reproduz EXATAMENTE o cenário perigoso: dois usuários distintos na mesma
gestora, editar a senha de UM, confirmar que o OUTRO continua logando com a
senha antiga dele E que o editado passa a logar só com a senha nova (a
antiga dele deixa de funcionar):

```python
def test_trocar_senha_de_um_usuario_nao_afeta_outro(client, db):
    """Regressão direta da suspeita levantada em teste manual (ver
    plans/003-verificar-isolamento-senha-usuarios.md): trocar a senha do
    usuário B não pode mudar a senha do usuário A, nem deixar a senha
    antiga de B ainda válida."""
    gestora, gestor = _gestora_com_usuario(db, matricula="GESTOR-N1", gestora_nome="Gestora N")
    usuario_a = Usuario(matricula="USER-A1", nome="Usuario A", senha_hash=auth.hash_senha("senha-a-original"),
                       papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    usuario_b = Usuario(matricula="USER-B1", nome="Usuario B", senha_hash=auth.hash_senha("senha-b-original"),
                       papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    db.add_all([usuario_a, usuario_b])
    db.flush()
    usuario_b_id = usuario_b.id

    _login(client, "GESTOR-N1")
    resp = client.patch(f"/usuarios/{usuario_b_id}", json={"senha": "Senha-B-Nova-123!"},
                        headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    db.refresh(usuario_a)
    db.refresh(usuario_b)

    # A não pode ter mudado
    assert auth.verificar_senha("senha-a-original", usuario_a.senha_hash), \
        "BUG CONFIRMADO: trocar a senha de B alterou a senha de A"

    # B tem que estar com a senha NOVA (e a antiga tem que ter deixado de valer)
    assert auth.verificar_senha("Senha-B-Nova-123!", usuario_b.senha_hash)
    assert not auth.verificar_senha("senha-b-original", usuario_b.senha_hash)

    # end-to-end via login de verdade, não só hash direto
    client.cookies.clear()
    login_a = _login(client, "USER-A1", senha="senha-a-original")
    # _login() não retorna Response nesta suíte (ver assinatura) — se
    # precisar do status, adapte pra capturar o retorno de client.post
    # dentro de _login ou chame client.post direto aqui, seguindo o mesmo
    # corpo/headers que _login usa.
```

Note: `_login(client, matricula, senha="senha123")` neste arquivo **não
retorna** a `Response` (confira a assinatura em
`tests/test_usuarios_crud.py` antes de escrever a parte end-to-end acima —
se ela só faz `client.post(...)` sem `return`, ajuste o teste pra chamar
`client.post("/auth/login", ...)` diretamente e capturar o `resp.status_code
== 200`, seguindo o padrão de `_bootstrap_csrf_publico`/`_csrf_headers` já
usado em `tests/test_cadastro_convite.py` se for mais direto que reusar
`_login`).

Rode duas vezes: uma ANTES de escrever qualquer correção (só pra ver se
falha ou passa hoje), e documente o resultado literal (saída do pytest) no
commit message.

**Verificar**: `python -m pytest tests/test_usuarios_crud.py::test_trocar_senha_de_um_usuario_nao_afeta_outro -q` → **se passar**: a suspeita está refutada no nível testado — siga pro Passo 1b. **Se falhar**: você achou um bug real — pare aqui, NÃO tente corrigir dentro deste plano (ver STOP conditions), documente a asserção que falhou e o traceback completo, e reporte.

### Passo 1b — Se o Passo 1 passou: teste adicional cobrindo o cenário exato da narração (revogar sessão + trocar senha) (P0)

A narração original envolvia revogar a sessão ativa do usuário ANTES de
trocar a senha, e trocar a senha de si mesmo logo depois de editar outro
usuário. Adicione:

```python
def test_revogar_sessao_e_trocar_senha_em_sequencia_nao_vaza_entre_usuarios(client, db):
    gestora, gestor = _gestora_com_usuario(db, matricula="GESTOR-N2", gestora_nome="Gestora N2")
    usuario_a = Usuario(matricula="USER-A2", nome="Usuario A2", senha_hash=auth.hash_senha("senha-a2-original"),
                       papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    db.add(usuario_a)
    db.flush()
    usuario_a_id = usuario_a.id

    _login(client, "GESTOR-N2")
    resp = client.post(f"/usuarios/{usuario_a_id}/revogar-sessao", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    resp = client.patch(f"/usuarios/{usuario_a_id}", json={"senha": "Senha-A2-Nova-123!"},
                        headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    # a senha do PRÓPRIO gestor não pode ter mudado
    db.refresh(gestor)
    assert auth.verificar_senha("senha123", gestor.senha_hash), \
        "BUG CONFIRMADO: editar outro usuário alterou a senha do gestor logado"
```

(Confira o nome exato da rota de revogar sessão — `/usuarios/{id}/revogar-sessao` — contra `app.py` antes de rodar; se o nome for outro, ajuste, mas não pule este teste por causa disso.)

**Verificar**: mesmo raciocínio do Passo 1 — passar = refutado, falhar = STOP e reportar.

### Passo 2 — Investigar (não corrigir às cegas): papel do usuário criado diverge do pedido (P2)

Escreva SÓ um teste de reprodução, modelado em
`test_gestor_cria_usuario_na_propria_gestora` (já existe no arquivo, leia
antes de escrever o novo):

```python
def test_papel_do_usuario_criado_bate_com_o_pedido(client, db):
    _gestora_com_usuario(db, matricula="GESTOR-O1", gestora_nome="Gestora O")
    _login(client, "GESTOR-O1")
    resp = client.post("/usuarios", json={
        "matricula": "NOVO-O1", "nome": "Fulano", "papel": "analista",
        "senha": "Senha-Nova-123!",
    }, headers=_csrf_headers(client))
    assert resp.status_code == 201, resp.text
    assert resp.json()["papel"] == "analista"
```

Se passar (provável, já que a leitura de `criar_usuario_rota` não mostrou
bug), o achado da narração fica marcado como "não reproduzido — provável
confusão durante teste manual" e este passo termina aqui, sem mexer em mais
nada.

**Verificar**: `python -m pytest tests/test_usuarios_crud.py::test_papel_do_usuario_criado_bate_com_o_pedido -q` → passa.

### Passo 3 — "Meu Perfil": investigação leve de UX, sem implementação garantida (P2)

Este passo é diferente dos anteriores: não há uma correção especificada
porque a leitura desta sessão não foi funda o bastante em
`apps/web/src/app/(app)/perfil/page.tsx` pra prescrever uma mudança exata
(ver Hard Rule 3 do skill `improve` — não inventar precisão que não existe).

1. Leia `apps/web/src/app/(app)/perfil/page.tsx` inteiro.
2. Confirme com uma leitura simples: a tela mostra em algum lugar visível o
   papel do usuário logado (ex.: "Gestor", "Analista", "Compliance") de
   forma clara? Existe algum link/botão pra ir à tela de criação de usuário
   (`/admin/usuarios`) quando `usuario.papel` é `gestor` ou `compliance`?
3. **Se a resposta às duas perguntas acima for "não" e a mudança for
   pequena** (adicionar um `<Badge>` com o papel + um `<Link
   href="/admin/usuarios">` condicional ao papel, seguindo o padrão de
   outros links condicionais por papel já existentes no arquivo — ex. a
   guarda de papel citada em "Estado atual" acima), implemente. Siga os
   tokens de `apps/web/DESIGN.md` pra cor/tipografia do badge.
4. **Se a tela já mostra isso** (a leitura anterior desta sessão pode estar
   errada) **ou se a mudança exigir reestruturar o layout da página**, NÃO
   implemente — documente o achado real (com trecho do JSX lido) no relato
   final e pare, deixando como candidato a um plano futuro dedicado.

**Verificar** (só se implementou): `cd apps/web && npx tsc --noEmit` → exit 0; `npx eslint src/app/\(app\)/perfil/page.tsx` → exit 0.

## Plano de testes

Já detalhado nos Passos 1, 1b e 2 acima — são o entregável principal deste
plano, não um adicional. Resumo:

- `test_trocar_senha_de_um_usuario_nao_afeta_outro`
- `test_revogar_sessao_e_trocar_senha_em_sequencia_nao_vaza_entre_usuarios`
- `test_papel_do_usuario_criado_bate_com_o_pedido`

Verificação final: `cd services/prisma-api && source ../../.venv/bin/activate && python -m pytest -q` → todos passam, incluindo os 3 novos.

## Critérios de conclusão

- [ ] Os 3 testes novos existem em `tests/test_usuarios_crud.py` e passam
- [ ] `python -m pytest services/prisma-api -q` → sem regressão (baseline 195 passed/5 skipped)
- [ ] O relatório final do executor declara explicitamente, por escrito, se
      cada uma das 3 suspeitas foi CONFIRMADA ou REFUTADA (não deixe
      implícito no código do teste só)
- [ ] Se alguma suspeita foi CONFIRMADA, nenhuma tentativa de correção foi
      feita neste plano além de documentar — a correção fica pra um plano
      novo (ver STOP conditions)
- [ ] Nenhum arquivo fora do escopo foi modificado (`git status`)
- [ ] `plans/README.md` atualizado

## STOP conditions

Pare e reporte (não improvise) se:

- Qualquer um dos testes dos Passos 1/1b falhar — ou seja, se você
  CONFIRMAR um bug real de contaminação de senha entre usuários. Isso é
  segurança num produto financeiro regulado; a correção certa depende de
  entender a causa raiz (SQLAlchemy identity map reusando objeto errado?
  cache de sessão HTTP? algo em `auth.hash_senha`/`verificar_senha`
  compartilhando estado?) — não é pra tentar 2-3 fixes às cegas até o teste
  passar. Documente o traceback completo e pare.
- O nome de alguma rota citada (`/usuarios/{id}/revogar-sessao`, `/usuarios`
  POST, `/usuarios/{id}` PATCH) não bater com o que existe em `app.py` —
  ajuste o nome no teste, mas se o COMPORTAMENTO também parecer diferente do
  descrito em "Estado atual", pare e reporte o diff antes de prosseguir.
- O Passo 3 exigir entender um fluxo de autorização/RBAC que não está
  descrito neste plano — não invente regra de negócio; documente a dúvida e
  pare.

## Notas de manutenção

- Se o Passo 1 confirmar um bug real, o próximo passo natural (fora deste
  plano) é: (a) reproduzir também via `TestClient` fazendo login real como
  cada usuário (não só checar o hash no banco) pra garantir que não é um
  problema de cache de JWT/cookie; (b) checar se `SessionLocal`/`get_db` tem
  algum escopo de sessão compartilhado entre requisições concorrentes do
  mesmo `TestClient` que pudesse mascarar OU causar o bug artificialmente —
  ou seja, também vale rodar o mesmo teste manualmente via `curl`/navegador
  contra a API rodando de verdade, não só via `TestClient`, pra descartar um
  artefato do próprio ambiente de teste.
- Este plano é deliberadamente pequeno e cético — ele existe pra transformar
  uma suspeita verbal, levantada em meio a um teste manual confuso, em um
  fato verificável. Trate um resultado "refutado" como um resultado bom e
  completo, não como um passo intermediário pra achar outra coisa.
