"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Gauge, Layers, MessagesSquare, FileText, Upload } from "lucide-react";
import { PrismaWordmark } from "@/components/brand/logo";
import { cn } from "@/lib/utils";

const NAV = [
  { grupo: "Análise", itens: [
    { href: "/", label: "Cockpit", icon: Gauge },
    { href: "/atribuicao", label: "Atribuição", icon: Layers },
    { href: "/copiloto", label: "Pergunte ao Prisma", icon: MessagesSquare },
  ]},
  { grupo: "Saídas", itens: [
    { href: "/relatorio", label: "Relatório", icon: FileText },
    { href: "/standalone", label: "Modo standalone", icon: Upload },
  ]},
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="hidden w-[248px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
      <div className="flex h-16 items-center px-5">
        <Link href="/" aria-label="Prisma — início">
          <PrismaWordmark />
        </Link>
      </div>

      <nav className="flex-1 space-y-6 px-3 py-4">
        {NAV.map((sec) => (
          <div key={sec.grupo}>
            <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/70">
              {sec.grupo}
            </p>
            <ul className="space-y-1">
              {sec.itens.map((item) => {
                const active = path === item.href;
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-150",
                        active
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "text-sidebar-foreground/80 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-[18px] w-[18px] transition-colors",
                          active ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
                        )}
                        strokeWidth={1.75}
                      />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-4">
        <div className="flex items-center gap-2.5 rounded-lg bg-sidebar-accent/40 px-3 py-2.5">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--success)] opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--success)]" />
          </span>
          <div className="leading-tight">
            <p className="text-xs font-medium text-foreground">Núcleo cognitivo ativo</p>
            <p className="text-[10px] text-muted-foreground">RAG + guardrail · auditável</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
