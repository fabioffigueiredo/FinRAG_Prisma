# Design

Documento gerado a partir do sistema de design real já implementado em `apps/web/src/app/globals.css` (identidade "Obsidian Terminal") — não é um ponto de partida especulativo, é a captura do que já está em produção, servindo de base para a Stage de login/admin.

## Color

Tokens semânticos via CSS custom properties (`@theme inline`, Tailwind v4), nunca hex cru em componente.

**Claro (institucional, padrão):**
- `--background: #f4f5f7` · `--foreground: #1a1c1c` · `--card: #ffffff`
- `--primary: #003366` (navy) · `--primary-foreground: #ffffff`
- `--warning: #fdb913` / `--ring: #fdb913` (âmbar — único acento vivo, uso restrito a ação primária/estado)
- `--success: #0a7f52` · `--destructive: #ba1a1a`
- `--border: #e2e5ea` · `--accent: #eaf0f7` (tint neutro, **não confundir com o âmbar**)

**Escuro (teal como acento vivo):**
- `--background: #0a1120` · `--foreground: #e7eefb` · `--card: #101a2e`
- `--primary: #2dd4bf` (teal) · `--warning`/`--ring` seguem `#fdb913` (âmbar constante nos dois temas)
- `--border: rgba(159, 183, 222, 0.14)` (hairline translúcida, não sólida)

Estratégia de cor: **Restrained** (produto) — um acento (âmbar) usado só em CTA primário, seleção ativa e indicadores de estado; nunca decorativo, nunca gradiente.

## Typography

- **Display/números:** Fraunces (`--font-display` → `var(--font-fraunces)`) — reservado para headline de login/momentos de marca e para números financeiros grandes (`.font-display`). Nunca em label/botão de UI comum.
- **UI/corpo:** Geist Sans (`--font-sans`).
- **Dados tabulares:** Geist Mono (`--font-mono`) + utilitário `.tabular` (`font-variant-numeric: tabular-nums`) em toda célula numérica/matrícula.
- Escala fixa em rem (não fluida) nas telas de produto — display fluido só na headline do login.

## Radius & Elevation

- `--radius: 0.5rem` base; `--radius-sm/md/lg/xl` derivados (`calc(var(--radius) ± Npx)`).
- Sem `box-shadow` decorativo por padrão — `.card-surface` usa borda + halo sutil só no hover (claro: sombra mínima; escuro: halo teal). Tabelas devem migrar para a técnica "shadow-as-border" (`box-shadow: 0 1px 0 var(--border)` no lugar de `border-b`) — hairline sem drop-shadow.

## Motion

Curvas de desaceleração natural, **nunca bounce/elastic**: `--ease-out-quart`, `--ease-out-quint`, `--ease-out-expo`. Utilitários existentes: `.animate-rise` (entrada padrão, 0.5s, suporta stagger via `--i`), `.prisma-caret` (streaming), `.prisma-draw`/`.prisma-fade-in`/`.prisma-dot-pop` (gráficos). `prefers-reduced-motion: reduce` já é honrado globalmente (bloco `@media` em `globals.css`).

## Components (já existentes, reaproveitar antes de criar novo)

`avatar, badge, button, card, dialog, dropdown-menu, input, progress, scroll-area, select, separator, sheet, skeleton, table, tabs, textarea, tooltip` — shadcn `base-nova` (Base UI, prop `render=`, **nunca `asChild`**). `Button` é CVA (`variant`: default/outline/secondary/ghost/destructive/link; `size`: default/xs/sm/lg/icon*) — Stage 4 adiciona `variant="warning"` para o CTA único de login.

Também já existentes: `label`, `checkbox`, `field`/`form` (FieldGroup), `command` (paleta Cmd+K via `components/ui/command.tsx` + `components/app/command-palette.tsx` — único primitivo que foge do padrão Base UI, `cmdk`). Nada pendente da lista original do Stage 4.

## Layout

Shell existente: `Sidebar` + `Topbar` (desktop), `MobileNav`/`MobileTabbar` (mobile) — vivem em `apps/web/src/components/app/`. Login vive **fora** desse shell (rota `/login`, sem sidebar/topbar). Painel admin estende o shell existente com filtro por papel (`gestor`/`compliance` veem "Administração"; `analista` não vê).
