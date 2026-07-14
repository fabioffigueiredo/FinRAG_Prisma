# Deploy do Prisma na VPS — https://wiki.ioi.ia.br/prisma

Demo hospedada com **IA de nuvem (Groq, free tier)** — a VPS não precisa de GPU
nem Ollama. Os embeddings caem automaticamente para `sentence-transformers`
(CPU). Dados 100% fictícios.

## Pré-requisitos na VPS
- Docker + Docker Compose (`docker --version`, `docker compose version`);
- `wiki.ioi.ia.br` servida pelo container **`ops-wiki-caddy`** (Caddy 2, NÃO
  nginx — `deploy/nginx-prisma.conf` é só referência histórica, desatualizada);
- Uma chave Groq (grátis em https://console.groq.com/keys), em `.env` na raiz
  do repo clonado (`GROQ_API_KEY=...`), nunca commitada.

## Passo a passo

```bash
# 1. Clonar o repositório na VPS
git clone https://github.com/fabioffigueiredo/FinRAG_Prisma.git
cd FinRAG_Prisma
echo "GROQ_API_KEY=gsk_suachave" > .env

# 2. Criar a rede externa (só na 1ª vez) e conectar o Caddy do ops-wiki nela
docker network create prisma-net
docker network connect prisma-net ops-wiki-caddy

# 3. Subir os containers (nomes fixos prisma-api/prisma-web, rede prisma-net)
docker compose -f deploy/docker-compose.yml up -d --build
#   prisma-web -> 127.0.0.1:3100   |   prisma-api -> 127.0.0.1:8000  (só localhost)

# 4. Conferir
curl -s http://127.0.0.1:8000/health        # {"status":"ok",...}
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3100/prisma   # 200
```

```caddyfile
# 5. Adicionar a rota no Caddyfile do ops-wiki (/srv/bb-asset-mirror/ops-wiki/Caddyfile):
#   handle /prisma* { reverse_proxy prisma-web:3100 }
#   handle /prisma/api* { uri strip_prefix /prisma/api; reverse_proxy prisma-api:8000 }
# faça backup antes (Caddyfile.bak-prisma-<timestamp>) e recarregue:
docker exec ops-wiki-caddy caddy reload --config /etc/caddy/Caddyfile
```

Pronto: **https://wiki.ioi.ia.br/prisma**

## Como o gestor testa
- Abrir o link, trocar de fundo (Alfa/Beta/Gama), gerar a narrativa ao vivo,
  perguntar no copiloto, ver o Radar, os Sinais, a Auditoria.
- Motor de IA: **Nuvem (Groq)** por padrão; **Demo** (determinístico) como reserva.
  A opção "Local" fica oculta nesta hospedagem (é a que exige Ollama on-premise).

## Notas de segurança/governança
- Groq é nuvem: adequado porque a demo usa dados fictícios. Em produção com dados
  reais, usa-se o modo **Local** ou um modelo homologado internamente (backend
  pluggável) — ver `docs/GOVERNANCA_IA.md`.
- `GROQ_API_KEY` entra só como variável de ambiente no `docker compose`, nunca no
  repositório. Se a chave faltar/expirar, a demo degrada para o motor Demo sem cair.

## Atualizar a demo depois de um push
```bash
cd FinRAG_Prisma && git pull
GROQ_API_KEY=gsk_suachave docker compose -f deploy/docker-compose.yml up -d --build
```

## Alternativa sem Docker (systemd)
Se preferir sem Docker: rode a API com a venv (`uv`) via `systemd`, faça
`next build` + `next start -p 3100` no `apps/web` com as mesmas variáveis do
`Dockerfile.web`, e use o mesmo `nginx-prisma.conf`. Peça que eu gero os units.
