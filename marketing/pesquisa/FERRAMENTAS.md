# Pesquisa — Ferramentas de vídeo, voz e divulgação (jul/2026)

Critério: **gratuito ou com créditos gratuitos**, qualidade profissional, preferência
por rodar local (privacidade) e por integração com agente (MCP/CLI).

## Decisão do projeto
**Produção dos vídeos: Remotion + capturas reais do app** (pipeline próprio, já
comprovado nos vídeos do FinNLP — custo zero, controle total, identidade visual
consistente). Ferramentas abaixo são complementos ou alternativas pontuais.

## Vídeo — geração/edição

| Ferramenta | Tipo | Grátis? | Quando usar | Link |
|---|---|---|---|---|
| **Remotion** | Vídeo programático (React→MP4) | Livre p/ indivíduo | **Base dos nossos vídeos** (LinkedIn 9:16 e gestor 16:9) | remotion.dev |
| **Higgsfield MCP** | Geração IA (Veo 3.1, Sora 2, Kling…) via MCP no Claude | **150 créditos/mês** (~2 clipes Veo) | B-roll cinemático de abertura, thumbnail animada | higgsfield.ai/mcp |
| **Open-Generative-AI** | Estúdio self-hosted MIT, 200+ modelos | App grátis; modelos de ponta exigem chaves/créditos dos provedores | Explorar geração img/vídeo sem assinatura | github.com/anil-matcha/open-generative-ai |
| **CapCut Desktop** | Editor tradicional | Grátis (recursos Pro pagos) | Ajustes manuais finais, legendas rápidas, export vertical | capcut.com |
| **Descript** | Edição por texto | Free tier limitado (marca d'água/limites) | Cortar narração por transcrição | descript.com |
| **Clipchamp** | Editor web (Microsoft) | Grátis 1080p | Alternativa simples ao CapCut | clipchamp.com |

## Voz — narração e clonagem (você tem a voz gravada)

| Ferramenta | Tipo | Grátis? | Observação | Link |
|---|---|---|---|---|
| **ElevenLabs** | TTS/clonagem nuvem | 10k caracteres/mês no free | **Já usado** — seus 3 áudios (FinRAG/FinNLP/Prisma) são a fonte primária | elevenlabs.io |
| **Voicebox** | Estúdio local open-source (16k★) | 100% grátis/local | Clonar SUA voz no M4 sem nuvem — melhor candidato ao próximo teste | github (voicebox) |
| **OmniVoice (Xiaomi)** | TTS/clonagem open-source | Grátis/local (roda até em CPU) | Relatos de bom PT-BR; alternativa ao Voicebox | github/HF (omnivoice) |
| **Fish Speech V1.5** | TTS open-source | Grátis/local | Multilíngue forte; mais técnico de configurar | github (fish-speech) |
| **F5-TTS** | Clonagem zero-shot | Grátis/local (MPS/M4 ok) | Clona com ~10s de referência; qualidade varia em PT | github (F5-TTS) |
| macOS `say -v Luciana` | TTS do sistema | Grátis | **Fallback** do pipeline (robótico; só rascunho de timing) | — |

> Sua última tentativa de clonagem gratuita ficou ruim — os candidatos acima
> (Voicebox/OmniVoice) são de geração mais nova; vale um teste com 30–60s de
> gravação limpa. Enquanto isso, os áudios ElevenLabs são a fonte oficial.

## Skills/agentes instalados neste projeto

| Skill | O que faz | Instalação |
|---|---|---|
| **find-skills** (vercel-labs/skills) | Descobre skills públicas p/ qualquer tarefa (`npx skills find`) | `npx skills add vercel-labs/skills --skill find-skills` |
| **improve** (shadcn/improve) | Audita o código (read-only) e escreve planos p/ modelos baratos executarem | `npx skills add shadcn/improve` |

## Diretrizes LinkedIn (2026) aplicadas ao kit

- **Vídeo nativo** (upload direto) é favorecido pelo algoritmo; nada de link do YouTube.
- **Vertical 9:16** para o feed de vídeo curto; 16:9 para conteúdo denso/desktop.
- **Legendas queimadas obrigatórias**: >70% assistem sem som.
- Duração ideal do vídeo de feed: **60–90s**; nativo aceita até 15 min (desktop).
- **Carrossel/documento**: 1080×1350, 8–12 páginas, primeira página = gancho.
- Link externo **no 1º comentário**, não no corpo do post.
- Autoridade > viralidade: 3–5 pilares editoriais, cadência 2–3 posts/semana.
