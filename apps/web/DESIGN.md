# Design

Sistema visual do Prisma — identidade **"Obsidian Terminal"**. Captura o estado atual (fonte da verdade em `src/app/globals.css`) e a linguagem de movimento introduzida no redesign. Dark-first, produto.

## Theme

- **Mood:** terminal financeiro profissional. Ink quase-preto com profundidade por glows radiais ambientes; ouro como marca; mint/coral como semântica financeira (positivo/negativo). Sóbrio, denso onde precisa, calmo.
- **Estratégia de cor:** Restrained + acento único (ouro) para ações primárias, seleção e indicadores de estado. Cor de estado nunca decorativa.
- **Modo:** dark forçado (`<html class="dark">`); `next-themes` presente mas não usado para alternância.

## Color (tokens — `globals.css`)

| Papel | Token | Valor |
|---|---|---|
| Fundo | `--background` | `#070a11` |
| Superfície | `--card` | `#0e1320` |
| Popover | `--popover` | `#121826` |
| Sidebar | `--sidebar` | `#0a0e17` |
| Texto | `--foreground` | `#f3eee3` |
| Muted | `--muted-foreground` | `#9aa1b0` |
| **Marca (ouro)** | `--primary` | `#f0b952` |
| Positivo (menta) | `--success` | `#5eead4` |
| Negativo (coral) | `--destructive` | `#fb7185` |
| Charts | `--chart-1..5` | ouro / azul `#5b8def` / menta / violeta `#c4a6ff` / âmbar `#f4c26b` |
| Borda | `--border` | `rgba(232,224,208,0.1)` |

**Luz ambiente (fundo):** uma **única fonte de luz coerente** de ouro no canto superior direito, com falloff grande e suave, aprofundando no ink em direção ao canto inferior esquerdo (`radial-gradient`s empilhados + `background-attachment: fixed`). Direcional e intencional (ref. antigravity) — nunca pontos radiais dispersos. A luz é o motivo pelo qual os acentos de ouro (hairline/borda `border-primary/25`) parecem parte do sistema, não aleatórios.

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
