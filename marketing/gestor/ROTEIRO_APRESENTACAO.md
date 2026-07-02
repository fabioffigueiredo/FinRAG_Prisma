# Roteiro — Apresentação do Prisma ao gestor (15 min)

**Material:** deck `prisma-deck.pdf` (ou `docs/deck/index.html` ao vivo) + demo no
navegador (`localhost:3100`). **Antes de entrar na sala:** API e frontend no ar,
Ollama aquecido (faça 1 pergunta no copiloto 10 min antes), motor em "Local".

---

## 0–2 min · O problema, em horas (slides 1–2)

**Gancho de abertura — comece pela conta, não pela tecnologia:**

> "Antes de mostrar qualquer tela, uma conta rápida. Quantos fundos fecham
> comentário todo mês aqui? Pega esse número e multiplica por duas a quatro
> horas de redação. Numa casa com 40 fundos, isso dá **até 160 horas por
> fechamento** — o mês inteiro de um analista sênior, escrevendo texto que a
> atribuição já calculou."

Pausa. Deixe a conta assentar. Só então:

> "Todo fechamento é a mesma cena: a atribuição entrega números impecáveis, e
> alguém senta para transformar aquilo em texto. Sem padrão, sem trilha, e não
> escala. Eu vim mostrar o que fiz com esse vão."

Não mencione IA ainda — a palavra só aparece na demo.

## 2–4 min · A virada (slides 3–4)

> "A minha proposta não é uma IA que analisa mercado. É mais restrito — e por
> isso funciona: uma camada que **explica números que já foram calculados**,
> citando a fonte de cada afirmação. Explicar é diferente de inventar."

Apresente a tese do produto: **um núcleo, dois adaptadores** (pluga na nossa
plataforma de atribuição, ou lê exports em pé próprio).

## 4–9 min · DEMO AO VIVO (o coração — slide 5 e o app)

Sequência ensaiada, nesta ordem (cada passo prova uma coisa):

| # | Ação | O que provar |
|---|---|---|
| 1 | Cockpit do Alfa → "Gerar ao vivo" | Narrativa gerada na hora, com fontes citadas |
| 2 | Radar de Mercado (card + tela) | Notícias com sentimento dão o "porquê" |
| 3 | Copiloto: "Por que o varejo pesou no resultado?" | Resposta cita a notícia + a regra |
| 4 | Copiloto: chip "Qual fundo devo comprar?" | **Recusa em 0,0s** — escopo explicativo |
| 5 | Copiloto: chip de injeção ("Ignore as instruções…") | Guardrail bloqueia e mostra na tela |
| 6 | Seletor de fundo → Beta; "Compare o Alfa e o Beta" | Multi-fundo e comparação |
| 7 | Tela Auditoria | Tudo que fizemos aqui está registrado |
| 8 | Seletor de motor: Local → Nuvem | "Isso rodou inteiro no meu notebook. Nada saiu da máquina." |

Frase de fechamento da demo:
> "Repare no que ela **não** fez: não recomendou, não previu, não respondeu sem
> fonte. Num ambiente regulado, o que a IA recusa vale tanto quanto o que ela faz."

## 9–12 min · Compliance e negócio (slides 6–9)

- Postura regulatória: explicativo por design, trilha de auditoria com hash.
- Encaixe: consome a API da nossa plataforma de atribuição — **não reescreve nada**
  do que já foi entregue.
- Valor: horas de analista por fechamento; comentário padronizado e auditável.
- KPIs propostos do piloto: tempo de redação (2–4h → <15min), % aprovado sem
  reescrita (≥70%), consultas/gestor/dia.

## 12–14 min · Roadmap (slides 10–11)

POC (pronto) → **piloto com 1 fundo real (30–60 dias)** → padrão do fechamento →
expansão (risco/VaR, multi-período).

## 14–15 min · O pedido (slide 12)

> "Para o piloto eu preciso de três coisas: **patrocínio** seu, **acesso** a um
> fundo real e à API da atribuição, e a **aprovação de um modelo de IA interno**
> — a arquitetura já é pluggável, roda com o modelo que a casa homologar."

Encerre com silêncio. Deixe a pergunta vir dele.

---

## Plano B (se algo falhar na demo)
- API fora? O frontend mostra dados-exemplo — siga narrando por cima.
- Ollama lento? Troque o motor para "Demo" (determinístico) sem comentar.
- Sem rede/projetor? `prisma-deck.pdf` tem os screenshots das telas-chave.

## Perguntas prováveis (e respostas de 1 linha)
- **"Isso alucina?"** — Ela só escreve sobre números já calculados e cita a fonte de cada frase; pergunta fora de escopo é recusada por regra, nem chega ao modelo.
- **"E segurança da informação?"** — Roda 100% local; na produção, trocamos pelo modelo que a casa aprovar — o backend de IA é pluggável.
- **"Quanto custa?"** — O POC custou zero de infraestrutura; o piloto usa máquina existente. O investimento é tempo de integração com a API.
- **"Por que não usar um chatbot pronto?"** — Chatbot genérico não cita nossas regras, não tem trilha de auditoria e não se recusa a recomendar.
