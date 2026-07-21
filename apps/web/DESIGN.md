# Design

Sistema visual do Prisma. Captura o estado atual (fonte da verdade em `src/app/globals.css`) e a linguagem de movimento introduzida no redesign.

> **Nota de proveniência (2026-07-18, atualizada 2026-07-20):** este arquivo
> descrevia originalmente a paleta ink+ouro do POC inicial (commit `a071377`,
> 2026-07-02, dark forçado). O commit `d73f206` ("Redesign institucional",
> 2026-07-08) substituiu essa paleta pela institucional navy/teal abaixo, e
> passou a honrar `next-themes` de verdade (claro/escuro alternável, não mais
> dark forçado). As seções **Theme** e **Color** foram corrigidas nesta data
> para refletir o CSS real; o resto do arquivo (Typography/Motion/Components/
> Layout) já estava atualizado.
>
> **Decisão de produto (2026-07-20):** a paleta navy/teal institucional é
> **definitiva** (não é um estado transitório do redesign). O nome
> **"Obsidian Terminal" passa a nomear esta identidade** (navy/teal +
> âmbar como acento vivo) — consistente com `DESIGN.md` (raiz) e
> `apps/web/PRODUCT.md`, que já usavam o nome dessa forma. A paleta ink+ouro
> original fica só como nota histórica (POC pré-08/07), sem reivindicar o
> nome "Obsidian Terminal".

## Theme

- **Mood:** produto institucional para instituição financeira regulada. Claro como padrão (fundo neutro, navy como marca); escuro com teal como acento vivo. Âmbar constante como único acento "vivo" (CTA primário/estado) nos dois temas — nunca decorativo.
- **Estratégia de cor:** Restrained — um acento por tema (navy claro / teal escuro), usado só em ação primária, seleção ativa e indicadores de estado.
- **Modo:** claro/escuro alternável de verdade via `next-themes` (`ThemeProvider` em `app/layout.tsx`, toggle em `components/app/theme-toggle.tsx`) — `defaultTheme="light"`, `enableSystem`.

## Color (tokens — `globals.css`)

Tokens semânticos via CSS custom properties (`@theme inline`, Tailwind v4), nunca hex cru em componente.

**Claro (institucional, padrão):**
| Papel | Token | Valor |
|---|---|---|
| Fundo | `--background` | `#f4f5f7` |
| Superfície | `--card` | `#ffffff` |
| Texto | `--foreground` | `#1a1c1c` |
| **Marca (navy)** | `--primary` | `#003366` |
| Acento vivo (âmbar) | `--warning` / `--ring` | `#fdb913` |
| Positivo | `--success` | `#0a7f52` |
| Negativo | `--destructive` | `#ba1a1a` |
| Borda | `--border` | `#e2e5ea` |
| Accent (tint neutro) | `--accent` | `#eaf0f7` — **não confundir com o âmbar** |

**Escuro (teal como acento vivo):**
| Papel | Token | Valor |
|---|---|---|
| Fundo | `--background` | `#0a1120` |
| Superfície | `--card` | `#101a2e` |
| Texto | `--foreground` | `#e7eefb` |
| **Marca (teal)** | `--primary` | `#2dd4bf` |
| Acento vivo (âmbar) | `--warning` / `--ring` | `#fdb913` (constante nos dois temas) |
| Borda | `--border` | `rgba(159,183,222,0.14)` — hairline translúcida, não sólida |

## Typography

- **Display / números:** Fraunces (`.font-display`, pesos 400/500/600) — títulos e figuras grandes de KPI.
- **UI:** Geist — headings de seção, labels, corpo, botões.
- **Dados:** Geist Mono — IDs, timestamps, códigos, scores de citação.
- **`.tabular`** (`tabular-nums`) obrigatório em toda figura numérica.
- Escala de produto: rem fixo, ratio ~1.125–1.2. Sem clamp fluido em UI.

## Motion

Camada introduzida no redesign. Biblioteca: **`motion`** (sucessora do Framer Motion) para React; CSS/`tw-animate-css` para transições declarativas simples.

- **Durações (100/300/500):** 100–150ms feedback · 200–300ms mudança de estado · 300–500ms layout · 500–800ms entrada.
- **Easing:** `--ease-out-quart` `cubic-bezier(0.25,1,0.5,1)`, `--ease-out-quint` `(0.22,1,0.36,1)`, `--ease-out-expo` `(0.16,1,0.3,1)`. Nunca bounce/elastic.
- **Padrões:** stagger de listas (≤50ms/item, teto ~500ms); draw-in de gráficos (path/width); streaming de mensagens no chat; skeleton→conteúdo em crossfade; hairline de acento como material recorrente.
- **`prefers-reduced-motion`:** obrigatório — alternativa instantânea/crossfade em toda animação.

## Components

- **Primitivos:** shadcn-style sobre **Base UI** (`@base-ui/react`, não Radix) em `components/ui/*`. **Convenção:** usar os primitivos por padrão — `ui/button` para toda ação (dá `focus-visible` ring + press feedback grátis), `ui/table` para tabelas (Atribuição/Auditoria), `ui/tooltip` para dicas, `ui/sheet` para nav mobile. **Exceções deliberadas** (motion bespoke supera o primitivo, documentado): dropdown de fundo e segmented "Motor" do topbar (pílula deslizante via `layoutId`), barra de probabilidade dos Sinais (`scaleX` animado), chips de filtro do Radar (pílula `layoutId`), tbody de Atribuição (crossfade ao trocar estratégia). Não migrar cegamente: consistência é vocabulário visual, não uniformização de tudo.
- **Padrão de card:** `rounded-xl border border-border bg-card p-5`. Variante acento adiciona `border-primary/25` + hairline `bg-gradient-to-r from-transparent via-primary/60 to-transparent` no topo (detalhe-assinatura).
- **Estados por componente:** default/hover/focus/active/disabled/loading. Loading via Skeleton (não spinner solto). Empty states ensinam a interface.
- **Cor de estado:** sempre ícone + rótulo junto do mint/coral/âmbar.

## Layout

- App-shell: Sidebar 248px (`hidden md:flex`) + Topbar sticky (`backdrop-blur-xl`) + `main`. Cada página `mx-auto max-w-{4xl–7xl} space-y-6`.
- Responsividade estrutural (colapsar sidebar → Sheet mobile, tabelas com overflow), não tipografia fluida.
- Grids sem breakpoint: `repeat(auto-fit, minmax(280px,1fr))` quando servir.
