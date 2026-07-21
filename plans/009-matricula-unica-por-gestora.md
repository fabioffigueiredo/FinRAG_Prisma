# Plano 009 — `matricula` única por gestora, não globalmente (achado #15)

**Decisão de negócio já confirmada com o usuário (2026-07-20):** matrícula
é um identificador de RH interno de cada gestora — duas gestoras
diferentes PODEM ter cada uma um funcionário de matrícula "1234" sem
colidir. Hoje a coluna é `unique=True` global; deve virar
`UniqueConstraint(gestora_id, matricula)`.

**Dependência: execute este plano DEPOIS do plano 008 estar mergeado em
`feature/copiloto-analitico`.** Os dois tocam `app.py` em regiões
diferentes mas próximas o bastante pra valer a pena reduzir risco de
conflito de merge — crie o worktree deste plano a partir do commit que já
inclui o 008 mergeado, não do commit anterior. Confirme rodando
`git log --oneline -5` e checando que os commits do 008 aparecem antes de
começar.

## Por que isso é maior do que parece

A coluna `matricula` não é só um identificador de exibição — é a chave de
LOGIN. Hoje `auth.autenticar()` e as duas rotas que decodificam o cookie
de sessão (`obter_usuario_pre2fa`, `get_usuario_atual`) procuram o usuário
só por `matricula`, assumindo que existe no máximo 1 linha com aquele
valor no banco inteiro. Se a constraint virar por-gestora, esse
pressuposto quebra: duas linhas podem ter a mesma matrícula (em gestoras
diferentes), e uma consulta `db.scalar(select(Usuario).where(Usuario.matricula == x))`
pode devolver ambíguo ou o registro errado.

**Achado a favor:** o JWT já carrega `gestora_id` no payload
(`auth.py:61`, dentro de `criar_token`) — só não é usado nos pontos que
decodificam o token de volta. Isso significa que a maior parte do fix é
"usar um campo que já existe", não inventar um novo — exceto no login em
si (ali ainda não existe sessão/token, então o FORMULÁRIO de login precisa
perguntar a gestora, do mesmo jeito que o formulário de autocadastro já
faz).

## Arquivos-chave

- `services/prisma-api/db/models.py` — `Usuario.matricula` (linha ~96)
- `services/prisma-api/alembic/versions/` — nova migration (não edite as
  existentes)
- `services/prisma-api/auth.py` — `autenticar` (linha ~110-128),
  `criar_token`/`criar_token_pre2fa` (linha ~55-65, ~182-190),
  `obter_usuario_pre2fa` (linha ~209-225), `get_usuario_atual`
  (linha ~240-269)
- `services/prisma-api/app.py` — `LoginReq` (linha ~191-193),
  `_login_com_rate_limit`, `PRISMA_DEMO_MATRICULA` lookup (linha ~525)
- `apps/web/src/lib/api.ts` — `login()` (linha ~254-270)
- `apps/web/src/app/login/page.tsx` — formulário de login (estado
  `matricula`/`senha`, linhas ~125-201)
- `apps/web/src/app/login/__tests__/page.test.tsx` — vai precisar de
  ajuste pro novo campo obrigatório
- `apps/web/src/app/cadastro/cadastro-form.tsx` — **use como referência
  exata** do padrão de seletor de gestora (`Select`/`SelectTrigger`/
  `SelectContent`/`SelectItem`, populado via `listarGestorasPublico()`)

## Passo 1 — Migration

**Nome real da constraint atual no Postgres** (confirmado rodando
`SELECT conname FROM pg_constraint WHERE conrelid = 'usuario'::regclass AND contype = 'u';`
no banco de dev/teste desta sessão): `usuario_matricula_key`. Confirme de
novo antes de aplicar — se o plano 008 (achado #9) já rodou e o nome da
constraint de `convite_token` mudou, o de `matricula` não deveria ter
mudado junto (são constraints diferentes), mas confira mesmo assim.

Gere a migration com Alembic (não escreva à mão do zero — deixe o
autogenerate detectar a partir do `db/models.py` já editado no Passo 2):
```bash
cd services/prisma-api
/Users/fabiofigueiredo/Projetos/prisma/.venv/bin/python -m alembic revision --autogenerate -m "matricula unica por gestora, nao global"
```
Revise o arquivo gerado e AJUSTE pra ficar assim (nomeando as constraints
explicitamente — mesmo cuidado do achado #9 do plano 008, autogenerate
deixa `None` por padrão):
```python
def upgrade() -> None:
    op.drop_constraint("usuario_matricula_key", "usuario", type_="unique")
    op.create_unique_constraint("uq_usuario_gestora_matricula", "usuario", ["gestora_id", "matricula"])


def downgrade() -> None:
    # ATENÇÃO: se já existirem duas linhas com a mesma matrícula em
    # gestoras diferentes quando este downgrade rodar, ele vai falhar
    # (viola a constraint global que está sendo recriada) — isso é
    # esperado, não um bug da migration; documentar no PR/changelog.
    op.drop_constraint("uq_usuario_gestora_matricula", "usuario", type_="unique")
    op.create_unique_constraint("usuario_matricula_key", "usuario", ["matricula"])
```

## Passo 2 — `db/models.py`

Troque:
```python
    matricula: Mapped[str] = mapped_column(String(20), unique=True)
```
por:
```python
    matricula: Mapped[str] = mapped_column(String(20))
```
E adicione, na classe `Usuario`, um `__table_args__` com a constraint
composta (confira se `Usuario` já tem `__table_args__` — se tiver, some a
tupla nela, não crie um segundo):
```python
    __table_args__ = (
        sa.UniqueConstraint("gestora_id", "matricula", name="uq_usuario_gestora_matricula"),
    )
```
(confirme o alias de import de `sqlalchemy` já usado no arquivo — pode já
estar como `sa` ou por import nomeado direto; siga o que já existe, não
adicione um import duplicado.)

## Passo 3 — `auth.py`: autenticação e resolução de sessão passam a exigir `gestora_id`

**`criar_token`** (linha ~55) já inclui `gestora_id` — sem mudança.

**`criar_token_pre2fa`** (linha ~182) NÃO inclui — adicione:
```python
def criar_token_pre2fa(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": usuario.matricula,
        "gestora_id": usuario.gestora_id,
        "pre2fa": True,
        "iat": agora,
        "exp": agora + timedelta(minutes=PRE2FA_EXPIRA_MINUTOS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
```

**`autenticar`** (linha ~110) ganha o parâmetro `gestora_id`:
```python
def autenticar(db: Session, gestora_id: int, matricula: str, senha: str) -> Usuario | None:
    """Retorna o usuário se gestora+matrícula+senha baterem e a conta
    estiver ativa; None em qualquer outro caso — nunca revelo qual dos
    três está errado (evita enumeração)."""
    usuario = db.scalar(
        select(Usuario).where(
            Usuario.gestora_id == gestora_id,
            Usuario.matricula == matricula,
            Usuario.ativo.is_(True),
        )
    )
    if usuario is None:
        return None
    if not verificar_senha_com_lockout(usuario, senha):
        return None
    return usuario
```

**`obter_usuario_pre2fa`** (linha ~221) e **`get_usuario_atual`**
(linha ~261) — adicione o filtro por `gestora_id` do próprio payload
decodificado:
```python
    usuario = db.scalar(select(Usuario).where(
        Usuario.matricula == payload["sub"],
        Usuario.gestora_id == payload.get("gestora_id"),
    ))
```
Use `payload.get("gestora_id")` (não `payload["gestora_id"]`) nesses dois
pontos — tokens emitidos ANTES deste deploy não vão ter essa claim, e
`.get()` devolve `None`, que não bate com nenhum `gestora_id` real (a
comparação falha graciosamente, o usuário cai no 401 "não autenticado" já
existente ali, que é o comportamento certo: sessão antiga = precisa logar
de novo, não travar com `KeyError`).

## Passo 4 — `app.py`: `LoginReq` e rota de login

```python
class LoginReq(BaseModel):
    gestora_id: int
    matricula: str
    senha: str
```

Em `_login_com_rate_limit`, troque a chamada:
```python
    usuario = auth.autenticar(db, req.matricula, req.senha)
```
por:
```python
    usuario = auth.autenticar(db, req.gestora_id, req.matricula, req.senha)
```
(o resto da função — contador de bloqueio, commit, resposta — não muda.)

**`PRISMA_DEMO_MATRICULA`** (linha ~525, botão "Entrar com Microsoft" —
simulação, sempre loga a mesma conta fixa de demo): a busca
`db.scalar(_select(_Usuario).where(_Usuario.matricula == PRISMA_DEMO_MATRICULA))`
continua sem filtro de gestora de propósito — é uma conta de demonstração
fixa, existe só uma seed dela; troque `db.scalar` por
`db.scalars(...).first()` só como defesa (evita `MultipleResultsFound` se
algum dia existir mais de uma linha com essa matrícula em gestoras
diferentes) — não adicione seletor de gestora nesse botão, ele
propositalmente não pede nada ao usuário.

## Passo 5 — Frontend: `lib/api.ts` e `login/page.tsx`

**`lib/api.ts`** — `login()` ganha o parâmetro:
```ts
export async function login(gestoraId: number, matricula: string, senha: string): Promise<LoginResultado> {
  const csrf = getCsrfToken();
  try {
    const res = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
      body: JSON.stringify({ gestora_id: gestoraId, matricula, senha }),
    });
    ...
```
(resto da função sem mudança.)

**`login/page.tsx`** — no componente que tem `matricula`/`senha`
(linhas ~125-201), siga EXATAMENTE o padrão de
`apps/web/src/app/cadastro/cadastro-form.tsx` pro seletor de gestora
(import `listarGestorasPublico`/`GestoraPublica` de `@/lib/api`, `useState<GestoraPublica[]>`,
`useEffect` que popula no mount, `Select`/`SelectTrigger`/`SelectValue`/
`SelectContent`/`SelectGroup`/`SelectItem`). Adicione:
```tsx
const [gestoraId, setGestoraId] = useState("");
const [gestoras, setGestoras] = useState<GestoraPublica[]>([]);

useEffect(() => {
  listarGestorasPublico().then(({ gestoras }) => setGestoras(gestoras));
}, []);
```
Coloque o `Select` ANTES do campo de matrícula no formulário (ordem
lógica: primeiro identifico a empresa, depois meu usuário nela). Atualize
a chamada de `login()`:
```tsx
const resultado = await login(Number(gestoraId), matricula, senha);
```
E o `disabled` do botão de submit (linha ~201) pra também exigir
`gestoraId`:
```tsx
disabled={enviando || !gestoraId || !matricula || !senha}
```

**Teste existente `app/login/__tests__/page.test.tsx`** — vai quebrar
porque o formulário agora tem um campo obrigatório a mais. Leia o teste
primeiro, ajuste pra selecionar uma gestora (mock de
`listarGestorasPublico` retornando pelo menos uma opção) antes de
submeter — siga o padrão de mock que o arquivo já usa pras outras
chamadas de API.

## Verificação

```bash
cd services/prisma-api
/Users/fabiofigueiredo/Projetos/prisma/.venv/bin/python -m alembic upgrade head
/Users/fabiofigueiredo/Projetos/prisma/.venv/bin/python -m pytest tests/ -q
cd ../../apps/web
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/vitest run
```
Baseline: suíte backend deve seguir passando sem regressão (número exato
depende de quantos testes o plano 008 já tiver adicionado antes deste —
confirme o baseline rodando a suíte ANTES de começar este plano e comparando
depois). Frontend: `tsc` limpo, `vitest` passando incluindo o teste de
login ajustado.

**Teste novo a escrever** (`tests/test_cadastro_convite.py` ou um arquivo
`tests/test_login_multi_gestora.py` novo, seguindo o mesmo padrão de
fixture Postgres real): crie duas gestoras, um usuário com a MESMA
matrícula em cada uma, senhas diferentes, confirme que login com
`gestora_id` da primeira só autentica com a senha da primeira (e vice
versa) — esse é o teste que prova que a ambiguidade foi resolvida de
verdade, não só que a migration rodou.

## Nota de manutenção / risco de deploy

Este plano muda o formato do JWT de sessão (payload ganha `gestora_id`
obrigatório pra validação). **Ao fazer deploy, todo usuário com sessão
ativa vai precisar logar de novo** (o cookie antigo não tem a claim nova,
cai no `.get("gestora_id") is None` → não bate com nenhum `gestora_id`
real → 401). Isso é esperado e aceitável (sessões de POC/demo, sem SLA de
uptime de sessão), mas avise antes de fazer o deploy deste plano — não é
silencioso pro usuário final.
