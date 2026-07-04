import { TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

export function Kpi({
  label,
  value,
  sub,
  tone = "default",
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "default" | "positive" | "negative";
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        "group relative overflow-hidden card-surface p-4",
        accent && "border-primary/25",
      )}
    >
      {accent && (
        <span className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent" />
      )}
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
        {tone === "positive" && (
          <TrendingUp className="h-4 w-4 shrink-0 text-[var(--success)]" strokeWidth={2} aria-hidden />
        )}
        {tone === "negative" && (
          <TrendingDown className="h-4 w-4 shrink-0 text-[var(--destructive)]" strokeWidth={2} aria-hidden />
        )}
      </div>
      <p
        className={cn(
          "font-display tabular mt-2 text-2xl font-semibold leading-none sm:text-3xl",
          tone === "positive" && "text-[var(--success)]",
          tone === "negative" && "text-[var(--destructive)]",
          tone === "default" && "text-foreground",
        )}
      >
        {value}
      </p>
      {sub && <p className="mt-1.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export function SectionTitle({
  children,
  hint,
}: {
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="mb-3 flex items-baseline justify-between">
      <h2 className="text-sm font-semibold text-foreground">{children}</h2>
      {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
    </div>
  );
}
