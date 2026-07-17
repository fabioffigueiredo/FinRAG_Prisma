"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { Sheet, SheetTrigger, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { PrismaWordmark } from "@/components/brand/logo";
import { CoreStatus } from "@/components/app/core-status";
import { navParaPapel } from "@/lib/nav";
import { useSession } from "@/components/app/session-context";
import { cn } from "@/lib/utils";

export function MobileNav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const { usuario } = useSession();
  const nav = navParaPapel(usuario?.papel);

  // fecha ao navegar
  useEffect(() => {
    setOpen(false);
  }, [path]);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <button
            aria-label="Abrir navegação"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:text-foreground md:hidden"
          />
        }
      >
        <Menu className="h-5 w-5" strokeWidth={1.75} />
      </SheetTrigger>

      <SheetContent side="left" className="w-[280px] gap-0 bg-sidebar p-0">
        <div className="flex h-16 items-center px-5">
          <Link href="/" aria-label="Prisma — início">
            <PrismaWordmark />
          </Link>
        </div>
        <SheetTitle className="sr-only">Navegação</SheetTitle>

        <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-2">
          {nav.map((sec) => (
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
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                          active
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-sidebar-foreground/80 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
                        )}
                      >
                        {active && <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-primary" />}
                        <Icon
                          className={cn("h-[18px] w-[18px] shrink-0", active ? "text-primary" : "text-muted-foreground")}
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
          <CoreStatus />
        </div>
      </SheetContent>
    </Sheet>
  );
}
