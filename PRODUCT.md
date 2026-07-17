# Product

## Register

product

## Platform

web

## Users

Gestores, analistas e compliance de gestoras de fundos (asset managers) — profissionais que hoje recebem números de atribuição de performance de uma plataforma interna e precisam transformá-los em comentário de fundo para comitê e cliente. O papel `gestor` é o público primário: decide e assina a narrativa que vai para fora. `analista` é o operador do dia a dia (consulta, gera narrativa, tira dúvidas). `compliance` é o público secundário: audita — precisa ver trilha, fontes e guardrails, não operar. Contexto de uso: ambiente de trabalho, decisão sob pressão de prazo, dado sensível e regulado (nunca instituição real, dados fictícios).

## Product Purpose

O Prisma traduz o resultado da atribuição de performance (contribuição por estratégia/ativo vs. benchmark) em narrativa auditável: explica em linguagem natural de onde veio o retorno, responde perguntas com citações às fontes (RAG), classifica notícias de mercado por sentimento como apoio ao "porquê", e registra cada consulta em trilha de auditoria (fontes, motor, latência, hash). Sucesso é reduzir o tempo entre "número pronto" e "comentário publicável" sem perder rastreabilidade — e sem nunca recomendar (guardrail explícito: "explica, não recomenda").

## Positioning

A atribuição de performance, explicada — não mais um dashboard de números, e sim a camada que transforma esses números em texto que um comitê confia.

## Brand Personality

Institucional, preciso, confiante — sóbrio sem ser frio. Fala como um terminal financeiro de verdade (Bloomberg, não um app de banco consumer): confiante o bastante para não precisar de ênfase visual, denso o bastante para servir quem já é fluente no domínio. Nunca alarmista, nunca informal.

## Anti-references

Não é um SaaS de IA genérico: nada de gradiente roxo-azul, glassmorphism decorativo, cards-em-cards, "hero metric" com número gigante + gradiente, ou grid idêntico de cards com ícone+título+texto. Não é fintech consumer (Nubank/Revolut): nada de cores vivas por decoração, mascotes, tom informal. Referência de restrição tipográfica e paleta: Mercury, Stripe Dashboard, Linear, Vercel/Geist, Ramp — commitment em uma cor de destaque só, hierarquia por peso e espaçamento, não por enfeite.

## Design Principles

Números primeiro, decoração nunca — todo dado financeiro é `tabular-nums`, toda tabela é densa antes de ser bonita. Uma cor de destaque, um propósito — o âmbar (`--warning`/`--ring`) marca ação primária e estado, nunca decoração. Confiança institucional sem ser frio — Fraunces carrega os números e momentos de marca (login, headlines), Geist carrega a interface; a mistura evita tanto o "frio demais" quanto o "genérico demais". Auditável em cada tela — RBAC e trilha de auditoria são primeira classe (aba própria), nunca escondidos em configurações.

## Accessibility & Inclusion

WCAG AA como piso: contraste ≥4.5:1 em texto de corpo (inclusive placeholder), ≥3:1 em texto grande; navegação completa por teclado (usuário de compliance frequentemente audita sem mouse); `prefers-reduced-motion` sempre respeitado; alvos de toque ≥44×44px mesmo sendo produto primariamente desktop (gestor pode conferir em tablet).
