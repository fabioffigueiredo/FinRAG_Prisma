# Avaliação independente do kit Prisma (duas bancas)

Artefatos avaliados: repositório público, README, post + carrossel, vídeos
(gestor/LinkedIn/1:1/tutorial), deck e roteiro de apresentação.

---

## Banca 1 — Gestor sênior de fundos (20 anos de mesa e comitê)

**Nota: 8,7 / 10**

**O que me convence:**
- O problema é real e foi formulado como quem já viveu fechamento: "a planilha
  fica pronta, o texto não" é a frase que eu diria. O gancho das 80–160 horas
  fala a minha língua — hora de analista é o meu custo mais caro.
- A postura regulatória é o diferencial: um sistema que **se recusa** a recomendar
  e registra trilha de auditoria com hash entende como banco funciona. Quem vende
  IA para mim raramente começa por aí.
- O encaixe "não substitui o que existe, explica o que existe" elimina a minha
  primeira objeção (proteção do investimento já feito).
- Multi-fundo com comparação e o radar de sentimento por estratégia são features
  que eu usaria numa segunda-feira de fechamento.

**O que me faz segurar a caneta:**
- Tudo roda sobre **dados fictícios**. Eu sei que é POC, mas até ver um fundo real
  com as regras reais de cálculo, considero promessa, não produto (o material é
  honesto sobre isso — conta a favor).
- Os números do slide de ganho são hipóteses declaradas. Certo em declarar; ainda
  assim, sem piloto medido, não levo ao comitê.
- Falta o "quem valida o texto": o fluxo de aprovação humana do comentário antes
  de ir ao cliente merece uma tela, não uma frase.

**Como eu avaliaria o autor:** contrataria a conversa no dia seguinte. Perfil raro:
entende a operação (atribuição por contribuição, FIC, benchmark) E entrega software
funcionando. Se o piloto confirmar 30% do que o deck promete, vira caso interno.

---

## Banca 2 — Staff Engineer de ML/IA (produção, LLMOps)

**Nota: 8,4 / 10**

**Sinais fortes de engenharia:**
- **Escopo inteligente**: restringir a IA a explicar números já calculados é a
  decisão de arquitetura certa para reduzir alucinação — mostra maturidade acima
  de "coloquei um chatbot".
- Guardrails em camadas (regex determinístico para escopo em 0,0s + sanitização de
  injeção + citações com score) e **auditoria com hash** — é o desenho que eu
  cobraria num design review.
- Backend de LLM pluggável (local Ollama ↔ nuvem via API key ↔ mock) com fallbacks
  em cada camada: a demo não morre sem rede. Isso é pensar em produção.
- Reuso honesto: núcleo RAG vendorizado e testado (13 testes), pipeline de
  sentimento aproveitado do projeto anterior com QA objetivo (Whisper validando a
  própria narração dos vídeos é um toque de quem automatiza qualidade).
- Repositório limpo: licença, badges, topics, dados 100% sintéticos, reprodução em
  poucos comandos.

**Onde eu apertaria no code review:**
- **Sem CI** (GitHub Actions rodando os 13 testes + tsc a cada push) — para repo
  público de portfólio, é o próximo passo óbvio e barato.
- Cobertura de testes é boa no backend novo, mas o frontend não tem testes; o
  índice FAISS é reconstruído no startup (ok no POC; em produção, persistir).
- Avaliação de retrieval existe (Precision@k no projeto anterior), mas o Prisma
  ainda não publica métricas próprias de RAG (groundedness/citação correta) —
  seria o diferencial técnico do repo.
- O classificador de sentimento herdado (SVM em corpus EN) rotulando PT foi
  contornado com LLM local — decisão documentada, mas um modelo PT dedicado é a
  evolução esperada.

**Como eu avaliaria o autor:** sênior em entrega, com instinto de produto. Não é
pesquisador de ML — é algo mais escasso: engenheiro que faz IA aplicada chegar
inteira na demo, com guardrails e trade-offs documentados. Passaria no meu bar
para nível pleno-sênior de AI Engineering; com CI + métricas de RAG publicadas,
sem ressalvas.

---

## Consolidado

| Artefato | Finanças | ML/IA |
|---|---|---|
| Repositório + README | 9,0 | 8,5 |
| Post + carrossel | 8,5 | 8,5 |
| Vídeo gestor | 9,0 | 8,0 |
| Vídeo LinkedIn/1:1 | 8,5 | 8,5 |
| Tutorial | 8,5 | 8,5 |
| Deck + roteiro | 9,0 | 8,0 |

**Prioridades para subir para 9,5:** (1) CI com badge verde; (2) piloto com 1 fundo
real e números medidos no lugar das hipóteses; (3) tela de aprovação humana do
comentário; (4) métricas de RAG publicadas no README.

---

# O caminho para o 10 — plano crítico, artefato por artefato

Sem complacência: 10 significa "nada a apontar num comitê hostil". Eis o que falta.

## Repositório (8,5–9,0 → 10)
- [x] Licença MIT, badges, topics, CI *(feito em 03/jul)*.
- [ ] **CI verde visível** — o badge só vale depois do primeiro run passar; conferir no Actions.
- [ ] **Métricas de RAG no README**: tabela Precision@k/groundedness sobre um conjunto de perguntas douradas do próprio Prisma (o método já existe do FinRAG — é reaplicar e publicar).
- [ ] **Release v0.1.0** com changelog — sinaliza disciplina de versionamento.
- [ ] **1 GIF de 10s no topo do README** (cockpit→pergunta→resposta) — decisão de 3 segundos do recrutador.
- [ ] Testes de frontend (2–3 com Playwright já instalado: rota, dropdown, chip de escopo).

## Vídeos (8,0–8,5 → 10)
- [ ] **Voz real em TODOS os vídeos** — o clone é 8; sua leitura real é 10. O roteiro de gravação está pronto (`marketing/audio/ROTEIRO_GRAVACAO.md`, ~3,5min de leitura). É o item de maior impacto por esforço.
- [ ] Música de fundo sutil (-28dB, sem vocal) + fade in/out — separa "bom" de "produzido".
- [ ] Thumbnail dedicada para YouTube (frame do título + logo, texto grande).
- [ ] 2–3 zooms/close-ups nos momentos-chave (selo de bloqueio, citação) em vez de tela cheia constante.

## Post + carrossel (8,5 → 10)
- [ ] Publicar e **iterar com dados**: o 10 de LinkedIn se mede em retenção/comentários; ajustar o gancho após o 1º post é parte do jogo.
- [ ] Slide 1 com um número no gancho ("160 horas por fechamento") — números param o scroll.
- [ ] Prova social: 1 depoimento (mesmo informal) de um colega de mesa após demo interna.

## Deck + apresentação ao gestor (8,0–9,0 → 10)
- [ ] **Piloto medido** — sem número real, o teto é 9. Com "no piloto, 12 comentários gerados, 9 aprovados sem edição, 3h→14min" o deck vira imbatível.
- [ ] Tela/fluxo de **aprovação humana** do comentário (review → aprovar → export) — fecha a objeção nº1 do compliance.
- [ ] Slide "Prisma Sinais" (fase 2) com o parecer preditivo — mostra visão de roadmap com governança (`marketing/pesquisa/ANALISE_SINAIS_PREDITIVOS.md`).
- [ ] Ensaio cronometrado com um ouvinte real uma vez antes do dia.

## Você, como candidato/autor (a avaliação que importa)
- Forças já visíveis: domínio do negócio + entrega ponta a ponta + honestidade técnica (hipóteses declaradas, limitações documentadas) — raro.
- Para o 10: **uma evidência de impacto real** (piloto, mesmo pequeno) e **uma peça pública com tração** (post publicado com engajamento orgânico). Portfólio perfeito sem uso real é 9; com um usuário de verdade, é 10.
