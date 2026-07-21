# Segurança do Prisma

Este documento descreve os controles de segurança implementados na área de
login e no painel administrativo, nos padrões esperados de uma instituição
financeira. Documenta o que **existe de verdade** no código — não o
aspiracional — incluindo as limitações conhecidas do POC.

## 1. Âncoras regulatórias e de engenharia

- **[Resolução BCB nº 85/2021](https://www.bcb.gov.br/content/about/legislation_norms_docs/BCB_Resolution_No_85_2021.pdf)**
  — dispõe sobre a política de segurança cibernética a ser adotada por
  instituições autorizadas a funcionar pelo Banco Central. É a âncora
  regulatória mais direta para infraestrutura de segurança (login, sessão,
  auditoria), diferente da CVM 20/30 já citada em
  [`docs/GOVERNANCA_IA.md`](GOVERNANCA_IA.md), que trata de recomendação de
  investimento.
- **[OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)**
  (Application Security Verification Standard) — não é reguladora, é o
  checklist de engenharia usado aqui para estruturar e verificar os controles
  abaixo por capítulo.

## 2. Controles implementados

### V2 — Autenticação

- Hash de senha com **bcrypt** (`auth.py::hash_senha`), nunca texto plano.
- Política de senha (mínimo 10 caracteres, maiúscula, minúscula, dígito,
  caractere especial) validada no servidor (`senha_policy.py`) **e** no
  cliente (`lib/senha.ts`, feedback imediato) — o servidor é quem de fato
  decide.
- **Lockout de conta**: 5 tentativas falhas → bloqueio de 15 minutos
  (`auth.py::autenticar`). A mensagem de erro é **sempre a mesma**, com ou
  sem bloqueio ativo — revelar o estado de bloqueio também é enumeração de
  conta (ASVS V2.1 — nunca confirmar a existência de uma matrícula).
- **Rate limiting** (`slowapi`): 5 requisições/minuto em `/auth/login`,
  `/auth/2fa/verificar`, `/auth/2fa/confirmar`, `/auth/login-microsoft-demo`,
  `/auth/cadastro` e `/auth/ativar-conta` — toda rota que aceita uma
  credencial (senha ou código TOTP) ou cria/ativa uma conta; 20/minuto em
  `GET /auth/convite/{token}` (consulta pública, defesa em profundidade —
  o token em si já tem 256 bits de entropia).
- **2FA (TOTP, RFC 6238)** obrigatório para os papéis `gestor` e
  `compliance` — nunca para `analista`, mantendo o fluxo de operação diária
  enxuto. Enrollment em duas etapas (`/auth/2fa/iniciar` gera o segredo sem
  ativar; `/auth/2fa/confirmar` só ativa depois de um código real validado,
  provando que o usuário configurou certo). Login em duas etapas usa um
  cookie **separado** (`prisma_pre2fa`, 5 min) do cookie de sessão — um
  token pendente de 2FA nunca abre nenhuma outra rota protegida.
- **Login "Entrar com Microsoft"** é uma **simulação de demonstração** —
  documentado explicitamente no código (`app.py::login_microsoft_demo`) e na
  UI. Não é OAuth/OIDC real, não fala com Azure AD, sempre autentica a mesma
  conta fixa (`PRISMA_DEMO_MATRICULA`, papel `analista` de propósito, nunca
  aciona 2FA).
- CSRF (double-submit cookie) protege toda rota de mutação, incluindo login
  — o próprio `/auth/csrf` é chamado ao montar a página, antes de existir
  sessão, fechando o vetor de login CSRF.
- **Troca de dispositivo de 2FA self-service** (`POST /auth/2fa/iniciar` com
  `totp_ativado=True`) exige **step-up**: a senha atual precisa ser
  confirmada de novo antes do segredo TOTP ser sobrescrito — um cookie de
  sessão roubado sozinho não basta pra sequestrar o 2FA. Primeiro enrollment
  não exige nada além do papel (não há segredo anterior pra proteger).

### Cadastro, convite e ativação de conta

Dois fluxos convergem no mesmo mecanismo de token de ativação:

1. **Autocadastro** (`POST /auth/cadastro`, público, rate-limited) — cria um
   usuário `papel=analista`, `status_cadastro=pendente`, `ativo=False`. Um
   gestor/compliance aprova (`POST /usuarios/{id}/aprovar`, pode ajustar o
   papel) ou rejeita (`POST /usuarios/{id}/rejeitar`).
2. **Convite direto do gestor** (`POST /usuarios/convite`) — cria o usuário
   já aprovado/ativo, sem etapa de aprovação; o gestor já decidiu o papel na
   hora.

Ambos terminam no mesmo lugar: um **token de ativação de uso único**
(`secrets.token_urlsafe(32)`, mesma primitiva do CSRF), expiração de 48h
(`convite.TOKEN_EXPIRA_HORAS`), embutido num link (`/ativar-conta/{token}`).
`POST /auth/ativar-conta` valida o token, deixa o usuário escolher a própria
senha e já emite sessão — **nunca** uma senha (temporária ou não) trafega
por e-mail, seguindo o
[OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html).
Envio de e-mail via API REST do SendGrid (`convite.py::enviar_email_ativacao`)
— nunca lança: se falhar (ou as env vars não estiverem configuradas), a rota
de aprovação/convite **sempre devolve o link também na resposta**, rede de
segurança que o gestor pode copiar manualmente.

### V3 — Gestão de sessão

- Cookie de sessão **httpOnly**, `Secure` em produção
  (`PRISMA_ENV=production`), `SameSite=Lax`, JWT assinado (`PRISMA_JWT_SECRET`
  — falha rápido se ausente em produção).
- **Revogação de sessão**: `get_usuario_atual` passa a consultar o banco em
  toda request autenticada (não é mais um JWT puramente stateless) e compara
  o `iat` do token com `Usuario.sessao_revogada_em`. Um gestor/compliance
  pode derrubar a sessão ativa de outro usuário na hora
  (`POST /usuarios/{id}/revogar-sessao`), sem esperar o JWT expirar sozinho.
- **Troca de senha forçada**: `trocar_senha_no_proximo_login` bloqueia
  acesso a qualquer rota da aplicação (gate em `(app)/layout.tsx`) até a
  senha ser trocada — checado **antes** até da matrícula obrigatória em 2FA,
  já que senha temporária/vazada é o risco mais urgente.
- Logout limpa os três cookies (`prisma_session`, `prisma_csrf`,
  `prisma_pre2fa`) e é auditado.

### V7 — Log e trilha de auditoria

- `audit.registrar_evento()` grava, por evento: horário, rota, matrícula do
  ator e descrição — reaproveita o mesmo armazenamento (Postgres + fallback
  JSONL) já usado pela auditoria de consultas RAG do produto.
- Eventos cobertos: login (sucesso/falha/bloqueio/via Microsoft-demo),
  logout, troca de senha, upload de avatar, enrollment/confirmação/verificação
  de 2FA, criação/edição de usuário, força de troca de senha, revogação de
  sessão.
- **Histórico de acessos por usuário** exposto no admin
  (`GET /usuarios/{id}/historico-acessos`, RBAC gestor/compliance + checagem
  de tenant) — usado na seção "Histórico de acessos" do dialog de edição.

### Headers de segurança (correlato a V14 — configuração)

`security_headers.py`: `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`
sempre; `Strict-Transport-Security` (HSTS) quando `PRISMA_ENV=production` —
mesmo gate que já controla o `secure=` dos cookies.

## 3. Limitações conhecidas do POC

Documentadas de propósito, não escondidas:

- **`totp_secret` em texto plano** no banco. Mesmo limite de confiança que o
  resto do app já assume (isolamento é por linha/tenant, não por
  criptografia em repouso). Produção real: `cryptography.fernet` com chave
  de secrets manager.
- **Rate limiter em memória** (`slowapi` sem `storage_uri`) — não funciona
  corretamente com múltiplas instâncias do backend atrás de um
  load-balancer (cada instância tem seu próprio contador). Trocar por Redis
  é `storage_uri="redis://..."` na criação do `Limiter`, sem mexer nas
  rotas.
- **Sem CSP** (Content-Security-Policy) — Next.js (scripts inline de RSC) +
  Tailwind exigiriam uma política com nonce/allowlist cuidadosamente
  ajustada; não implementado aqui para não arriscar quebrar a demo com uma
  CSP mal calibrada.
- **Sem proteção completa de "último admin"** — existe só uma guarda
  simples contra autodesativação (um usuário não pode desativar a própria
  conta), herdada de uma sessão anterior. Não impede, por exemplo, que o
  último gestor ativo de uma gestora seja desativado por outro gestor.
- **Login "Entrar com Microsoft" é simulação** — ver seção 2, V2.
- **`SENDGRID_API_KEY`/`SENDGRID_FROM_EMAIL` não configurados** faz
  `enviar_email_ativacao` sempre devolver `False` sem lançar — degrada pro
  link-na-resposta (ver seção "Cadastro, convite e ativação de conta").
  Nunca commitado; tratamento igual ao de `PRISMA_JWT_SECRET`/`GROQ_API_KEY`
  no `.env` da VPS.

## 4. Onde cada controle vive no código

| Controle | Arquivo |
|---|---|
| Hash/política de senha, lockout, 2FA, revogação | `services/prisma-api/auth.py` |
| Rotas de auth/2FA/admin/cadastro | `services/prisma-api/app.py` |
| Token de ativação + envio de e-mail (SendGrid) | `services/prisma-api/convite.py` |
| Política de senha (regras) | `services/prisma-api/senha_policy.py` |
| Headers de segurança | `services/prisma-api/security_headers.py` |
| Auditoria | `services/prisma-api/audit.py` |
| Gate de telas obrigatórias | `apps/web/src/app/(app)/layout.tsx` |
| Menu do usuário / logout | `apps/web/src/components/app/user-menu.tsx` |
| Autocadastro público | `apps/web/src/app/cadastro/` |
| Ativação de conta via link | `apps/web/src/app/ativar-conta/[token]/` |
