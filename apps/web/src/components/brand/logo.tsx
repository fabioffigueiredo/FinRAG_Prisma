import { cn } from "@/lib/utils";

/**
 * Marca do Prisma: um prisma decompõe um raio (o retorno) em espectro
 * (as estratégias). Símbolo autoral — não é ícone genérico.
 */
export function PrismaMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={cn("h-7 w-7", className)}
      aria-hidden="true"
    >
      {/* raio de entrada */}
      <path d="M1 15 H10" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" />
      {/* prisma (triângulo) */}
      <path
        d="M11 22 L20 6 L23 22 Z"
        stroke="var(--primary)"
        strokeWidth="1.75"
        strokeLinejoin="round"
        fill="color-mix(in oklab, var(--primary) 12%, transparent)"
      />
      {/* espectro de saída */}
      <path d="M23 13 L31 9"  stroke="var(--chart-3)" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M23 16 L31 15" stroke="var(--chart-1)" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M23 19 L31 22" stroke="var(--chart-2)" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M23 21.5 L31 27" stroke="var(--chart-4)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function PrismaWordmark({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <PrismaMark />
      <div className="flex flex-col leading-none">
        <span className="font-display text-[17px] font-semibold tracking-tight text-foreground">
          Prisma
        </span>
        <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
          Attribution Intelligence
        </span>
      </div>
    </div>
  );
}
