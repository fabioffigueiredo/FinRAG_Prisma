# Product

## Register

product

## Users

Gestores de fundos, comitês de investimento e clientes finais que recebem o comentário de fundo. Contexto de uso: ambiente regulado, alta exigência de rastreabilidade, sob pressão de tempo para produzir o texto que explica o resultado do período. O usuário está numa tarefa (entender/explicar/aprovar atribuição de performance), não navegando por lazer.

## Product Purpose

Prisma é uma camada cognitiva que transforma o resultado da atribuição de performance de fundos em narrativa auditável: explica em linguagem natural de onde veio o retorno, responde perguntas com citações às fontes (RAG) e registra tudo em trilha de auditoria — podendo rodar 100% local e privado (Ollama). Fecha o vão entre os números que a plataforma de atribuição já entrega e o comentário de fundo que hoje é escrito à mão, devagar e sem trilha. Um núcleo, dois adaptadores: integrado (API da plataforma) ou standalone (exports CSV). Sucesso = o gestor confia no texto o bastante para levá-lo a comitê e cliente, com a fonte de cada afirmação a um clique.

## Brand Personality

Auditável, preciso, sóbrio. Confiança de terminal financeiro profissional — não de app de consumo. Três palavras: **auditável, preciso, calmo-confiante**. A interface deve evocar rigor e transparência ("explica, não recomenda"), nunca hype. Movimento e polimento existem para transmitir estado e credibilidade, não para entreter.

## Anti-references

- SaaS genérico cream/beige com eyebrow tracked em toda seção.
- IA de consumo chamativa (gradient text, glow decorativo, confete).
- Dashboards que "gritam" com cor saturada em tudo.
- Movimento decorativo que não comunica estado — o usuário está numa tarefa regulada.

## Design Principles

1. **A fonte a um clique.** Toda afirmação gerada carrega citação; a UI torna a proveniência sempre acessível, nunca escondida.
2. **Explica, não recomenda.** Guardrails de escopo e injeção são cidadãos de primeira classe na interface, com estado visual claro (verde fundamentado / coral bloqueado / âmbar fora-de-escopo).
3. **Rigor visível.** Números com `tabular-nums`, latência e hash à mostra — o produto pratica a auditabilidade que prega.
4. **Movimento com propósito.** Motion comunica estado (streaming, recuperação, draw-in de dados, transição de estado), nunca decora. 150–250ms na maioria; entradas mais longas só onde ganham.
5. **Melhorar sem descaracterizar.** A identidade "Obsidian Terminal" é ativo; evoluir por refinamento, não por substituição.

## Accessibility & Inclusion

- Respeitar `prefers-reduced-motion` em toda animação (alternativa em crossfade/instantâneo).
- Contraste: corpo ≥4.5:1, texto grande ≥3:1 sobre o ink profundo.
- Dark-first (forçado); cor de estado nunca é o único canal (ícone + rótulo acompanham mint/coral).
- pt-BR.
