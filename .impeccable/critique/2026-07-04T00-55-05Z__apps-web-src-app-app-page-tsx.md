---
target: Prisma app (redesigned surfaces)
total_score: 33
p0_count: 0
p1_count: 0
timestamp: 2026-07-04T00-55-05Z
slug: apps-web-src-app-app-page-tsx
---
# Critique — Prisma (app UI, redesenhado)

Register: product · target: superfícies redesenhadas (Cockpit representativo + Copiloto, shell, demais páginas).

## Design Health Score

| # | Heurística | Nota | Questão-chave |
|---|-----------|-------|-----------|
| 1 | Visibilidade do status | 4 | Streaming, loader de RAG encadeado, skeletons, spinners, nav ativa, latência. Sólido. |
| 2 | Sistema ↔ mundo real | 4 | Linguagem de domínio natural (cota, alpha, pp, benchmark), pt-BR. |
| 3 | Controle e liberdade | 3 | Copiloto sem limpar conversa / parar geração / copiar resposta. |
| 4 | Consistência e padrões | 3 | Primitivos `ui/*` instalados mas contornados (tabelas cruas, dropdown/segmented à mão, N tratamentos de botão). |
| 5 | Prevenção de erro | 3 | Guardrails (injeção/escopo) e aprovação humana são fortes; poucas ações destrutivas. |
| 6 | Reconhecer > lembrar | 4 | Nav com ícone+texto, chips de sugestão, tooltips de citação. |
| 7 | Flexibilidade/eficiência | 2 | Sem atalhos de teclado, sem command palette, sem trocar fundo/motor via teclado. |
| 8 | Estético e minimalista | 4 | Hierarquia limpa, cor com propósito, luz ambiente coerente. |
| 9 | Recuperação de erro | 3 | Fallbacks graciosos em toda a API + mensagens de guardrail claras; Copiloto não sinaliza fallback, sem "tentar de novo". |
| 10 | Ajuda e documentação | 3 | Hints contextuais + tooltips + subtítulos ensinam; sem docs dedicada. |
| **Total** | | **33/40** | **Good (faixa alta)** |

## Anti-Patterns Verdict

**LLM assessment:** NÃO parece AI-generated. Identidade "Obsidian Terminal" comprometida e distinta (ink + ouro + Fraunces em números display + mono em dados) — foge do default SaaS-cream, sem gradient text, movimento com propósito, luz de fundo agora coerente e direcional. Um usuário fluente em Linear/Stripe confiaria na interface. Único ponto borderline: densidade de micro-labels em caixa-alta com tracking (labels de KPI, "MOTOR", "PERÍODO", eyebrow do relatório) — dentro da norma de produto, mas presente.

**Deterministic scan:** `detect.mjs --json` sobre `apps/web/src/app` + `apps/web/src/components` (43 arquivos .tsx) → **exit 0, zero findings**. Nenhum tell de slop (gradient text, side-stripe, eyebrow scaffolding). LLM e detector concordam: limpo.

**Visual overlays:** Não apresentados — o MCP de browser está fixado no canal `chrome` (ausente, exige sudo). Inspeção visual feita via screenshots próprios (chromium do Playwright): Cockpit, Copiloto (empty/answer/loading), Atribuição, Sinais, Relatório, Standalone, mobile.

## Overall Impression

Visualmente excelente e agora bem animado — as três fases de redesign entregaram uma identidade coesa, motion com propósito e mobile funcional. O gap deixou de ser estético: agora é **robustez e consistência de sistema** (controles do chat, consolidação de primitivos, transparência de fallback), não mais aparência. Maior oportunidade: fechar a lacuna entre "lindo" e "à prova de uso real".

## What's Working

1. **Movimento comunica estado, não decora.** Streaming do Copiloto + loader de RAG encadeado + draw-in dos gráficos + skeletons = o produto "sente" as operações. Reduced-motion honrado globalmente.
2. **Postura de confiança regulada visível.** Guardrail (verde fundamentado / coral bloqueado / âmbar escopo), citações com score, latência à mostra, trilha de auditoria — a governança que o produto prega está na cara da UI.
3. **Luz ambiente coerente.** Fonte única de ouro no canto superior direito com falloff suave; os acentos de ouro nas bordas agora pertencem ao sistema.

## Priority Issues

- **[P2] Copiloto serve fallback silenciosamente.** Quando a API cai, `lib/api.ts` devolve uma resposta canned; o Copiloto a exibe como se fosse gerada ao vivo (o NarrativeCard sinaliza "narrativa · exemplo", o Copiloto não). Em produto auditável, servir exemplo como resposta fundamentada é risco de confiança. **Fix:** badge "modo exemplo / offline" na bolha quando `data.fallback`. → /impeccable harden
- **[P2] Vocabulário de componentes inconsistente.** `ui/table`, `ui/select`, `ui/tabs`, `ui/progress` instalados mas contornados (tabelas cruas em atribuição/auditoria, dropdown e segmented à mão no topbar, múltiplos tratamentos de botão). Mina consistência e manutenção. **Fix:** consolidar sobre os primitivos. → /impeccable polish
- **[P2] Zero aceleradores de power user.** Nenhum atalho de teclado, sem command palette, sem trocar fundo/motor por teclado, sem foco-no-composer por hotkey. Ferramenta analítica densa pede isso (persona Alex). **Fix:** palette (⌘K) + atalhos. → /impeccable harden
- **[P2] Copiloto sem controles de conversa.** Sem limpar/reiniciar, sem parar geração, sem copiar resposta, sem tentar de novo. Esperado num Q&A. → /impeccable clarify + harden
- **[P3] "Exportar PDF" é no-op.** Botão promete ação que não entrega (persona Riley) — e é justamente a saída de governança. **Fix:** implementar ou desabilitar com rótulo "em breve". → /impeccable harden
- **[P3] Empty states funcionais mas secos.** "Sem sinais — suba a API..." poderia ensinar mais e ser mais acolhedor. → /impeccable onboard

## Persona Red Flags

**Alex (Power User):** Sem atalhos para ações comuns. Não dá para trocar de fundo ou motor sem mouse. Sem command palette. Sem ações em lote. Único ganho: Enter-para-enviar no Copiloto. Vai sentir a ferramenta lenta para uso repetido.

**Sam (Accessibility):** Bom — reduced-motion honrado, gráficos com `aria-label`, cor de estado sempre com ícone+rótulo (não só cor), contraste do texto muted (~7:1) folgado. A verificar: foco-visível nos botões/itens de dropdown customizados; o typewriter atualiza o DOM repetidamente (pode reannunciar em leitor de tela — considerar `aria-live` controlado ou o texto instantâneo do reduced-motion). → /impeccable audit

**Comitê/Compliance (persona do projeto — audiência regulada):** Adora a trilha de auditoria, citações e guardrail proeminentes. Bandeira vermelha: "Exportar PDF" no-op e o fallback silencioso do Copiloto — ambos batem exatamente no ponto de confiança/governança que é o diferencial do produto.

## Minor Observations

- Indicador de nav ativa usa uma barra de 2px à esquerda — borderline vs. o ban de "side-stripe", mas defensável (rail de estado ativo + realce de fundo completo; padrão consagrado). Ciente, não é violação.
- Micro-labels em caixa-alta com tracking são numerosos; considerar variar a cadência (peso/tamanho) em vez de caixa-alta em toda parte.
- Mobile: nome do fundo trunca agressivo e a pílula "Local" do toggle Motor fica colada ao switcher — aceitável, refinável.
- `sonner` (toasts) e `next-themes` instalados mas sem uso — confirmações de ação (aprovar/exportar) seriam um uso natural do primeiro.

## Questions to Consider

- O que um Copiloto que assume "não sei / estou offline" com honestidade pareceria — mais confiável que um que sempre responde?
- Uma ferramenta usada todo fechamento de trimestre não deveria ter memória muscular (⌘K, atalhos)?
- A governança (aprovação, export, trilha) merece ser o momento mais polido do produto — está?
