# Kit LinkedIn — Prisma

> Diretrizes aplicadas (2026): gancho nas 2 primeiras linhas (antes do "ver mais");
> link **só no 1º comentário**; carrossel como documento PDF nativo; 3–5 hashtags
> de nicho; vídeo nativo vertical com legendas; cadência 2–3 posts/semana.

---

## POST PRINCIPAL (com o carrossel PDF anexado)

Todo fechamento de mês é a mesma cena: a atribuição de performance entrega uma
planilha impecável, e alguém passa horas transformando aquilo em texto para o
gestor, o comitê e o cliente.

Eu resolvi atacar exatamente esse vão.

Construí o Prisma, uma camada cognitiva que lê o resultado da atribuição e explica,
em português claro, de onde veio o retorno do fundo. Cada afirmação vem com a fonte
citada. Cada consulta fica registrada numa trilha de auditoria.

Três decisões de arquitetura que defendo:

1. A IA só escreve sobre números que já foram calculados. Explicar é diferente de
inventar, e num banco essa diferença é tudo.

2. Roda 100% local se precisar. Llama 3.1 + embeddings bge-m3 via Ollama, no meu
notebook. Nenhum dado sai da máquina.

3. Ela se recusa a recomendar. Pergunte "qual fundo devo comprar?" e o guardrail
responde que o escopo é explicativo. Compliance não é acessório, é design.

O projeto nasceu de dois trabalhos anteriores meus, um de NLP clássico (análise de
sentimento, grafo de entidades) e um de RAG com guardrails. O Prisma junta os dois
numa proposta de produto: números viram narrativa auditável.

Código aberto, dados 100% fictícios, demo reproduzível. Link no primeiro comentário.

Se você trabalha com fundos: quanto tempo do seu fechamento vai embora escrevendo
comentário de carteira?

#AtribuicaoDePerformance #RAG #LLM #MercadoFinanceiro #EngenhariaDeIA

---

## 1º COMENTÁRIO (postar imediatamente após publicar)

Repositório com o código, o roteiro de demo e a arquitetura:
https://github.com/fabioffigueiredo/FinRAG_Prisma

Stack: Next.js 16, FastAPI, FAISS, Ollama (llama3.1:8b + bge-m3), pipeline de
sentimento próprio. 13 testes, 3 motores de IA selecionáveis na interface.

---

## VARIANTE B — gancho técnico (para 2ª semana)

"IA em banco não pode alucinar" é fácil de falar e difícil de projetar.

No Prisma, a minha aposta foi restringir o problema: a IA nunca calcula nada.
Ela recebe números prontos da atribuição de performance e a única tarefa dela é
explicá-los, citando de onde tirou cada afirmação.

O resultado prático: respostas fundamentadas com score de recuperação, tentativa de
prompt injection bloqueada na tela, pergunta fora de escopo recusada em 0,0s (regra
determinística, nem chega no modelo) e trilha de auditoria com hash de cada resposta.

A parte que mais me orgulha não é o que ela responde. É o que ela se recusa a
responder.

Demo e código no primeiro comentário.

#EngenhariaDeIA #RAG #Guardrails #FinTech

---

## VARIANTE C — jornada (para depois da apresentação interna)

Três projetos, um caminho.

Primeiro o FinNLP: sentimento de notícias, grafo de entidades, NLP clássico bem
feito. Depois o FinRAG: busca semântica com citações e defesa contra prompt
injection. Agora o Prisma, que junta os dois sobre um problema real de negócio:
explicar a atribuição de performance de fundos.

O que aprendi no percurso: modelo é a parte fácil. O difícil é o resto — chunking
que respeita fronteira de sentença, guardrail que não dá falso positivo, auditoria
que convence um compliance, fallback para a demo não morrer na frente de ninguém.

Kit completo no primeiro comentário.

#CarreiraEmIA #NLP #RAG #PortfolioDeProjetos

---

## CADÊNCIA SUGERIDA (2 semanas)

| Dia | Conteúdo |
|---|---|
| D0 (ter, 8h–10h) | Post principal + carrossel PDF + 1º comentário com link |
| D0 +1h | Responder TODOS os comentários da primeira hora (golden hour) |
| D+2 (qui) | Vídeo vertical nativo (60–75s, legendado) com CTA para o repo |
| D+7 (ter) | Variante B (ângulo técnico/guardrails) |
| D+9 (qui) | Variante C (jornada) ou vídeo do gestor reeditado para feed |
| Contínuo | Comentar em posts de quant/asset management (autoridade fora do próprio feed) |

## CHECKLIST PRÉ-PUBLICAÇÃO
- [ ] Carrossel PDF anexado como "documento" (não imagens soltas)
- [ ] Link APENAS no 1º comentário
- [ ] Marcar o LinkedIn do repositório na seção Projetos/Destaques
- [ ] Vídeo: upload nativo, legenda queimada, capa com a 1ª frase visível
- [ ] Responder comentários na 1ª hora
