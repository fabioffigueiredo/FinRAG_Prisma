"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Gauge, Layers, MessagesSquare, Radar, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

/** Tab bar inferior (mobile) — navegação primária no padrão do design Stitch. */
const TABS = [
  { href: "/", label: "Cockpit", icon: Gauge },
  { href: "/atribuicao", label: "Atribuição", icon: Layers },
  { href: "/copiloto", label: "Copiloto", icon: MessagesSquare },
  { href: "/radar", label: "Radar", icon: Radar },
  { href: "/sinais", label: "Sinais", icon: TriangleAlert },
];

export function MobileTabBar() {
  const path = usePathname();
  return (
    <nav
      aria-label="Navegação principal"
      className="fixed inset-x-0 bottom-0 z-40 flex items-stretch border-t border-border bg-background/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden"
    >
      {TABS.map(({ href, label, icon: Icon }) => {
        const active = path === href;
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-1 py-2 text-[10px] font-medium transition-colors",
              active ? "text-primary" : "text-muted-foreground",
            )}
          >
            <Icon className="h-[22px] w-[22px]" strokeWidth={active ? 2.1 : 1.75} />
            <span className="tracking-tight">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
