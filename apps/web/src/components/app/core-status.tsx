import { cn } from "@/lib/utils";

/** Pílula "núcleo cognitivo ativo" — usada no rodapé da Sidebar e do MobileNav. */
export function CoreStatus({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div
      title={collapsed ? "Núcleo cognitivo ativo · RAG + guardrail" : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-lg bg-sidebar-accent/40",
        collapsed ? "h-9 w-9 justify-center p-0" : "px-3 py-2.5",
      )}
    >
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--success)] opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--success)]" />
      </span>
      {!collapsed && (
        <div className="leading-tight">
          <p className="text-xs font-medium text-foreground">Núcleo cognitivo ativo</p>
          <p className="text-[10px] text-muted-foreground">RAG + guardrail · auditável</p>
        </div>
      )}
    </div>
  );
}
