"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { PrismaWordmark } from "@/components/brand/logo";
import { CoreStatus } from "@/components/app/core-status";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { easeOutQuint } from "@/lib/motion";

export function Sidebar() {
  const path = usePathname();
  // índice global para escalonar a entrada de todos os itens de nav
  let idx = 0;
  return (
    <aside className="hidden w-[248px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
      <div className="flex h-16 items-center px-5">
        <Link href="/" aria-label="Prisma — início" className="transition-opacity hover:opacity-80">
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
                const i = idx++;
                return (
                  <motion.li
                    key={item.href}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.4, ease: easeOutQuint, delay: i * 0.04 }}
                  >
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-200",
                        active
                          ? "text-sidebar-accent-foreground"
                          : "text-sidebar-foreground/80 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
                      )}
                    >
                      {active && (
                        <motion.span
                          layoutId="nav-active"
                          className="absolute inset-0 -z-10 rounded-lg bg-sidebar-accent"
                          transition={{ type: "spring", stiffness: 420, damping: 34 }}
                        >
                          <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary" />
                        </motion.span>
                      )}
                      <Icon
                        className={cn(
                          "h-[18px] w-[18px] shrink-0 transition-[color,transform] duration-200 group-active:scale-90",
                          active
                            ? "text-primary"
                            : "text-muted-foreground group-hover:text-foreground group-hover:-translate-y-px",
                        )}
                        strokeWidth={1.75}
                      />
                      {item.label}
                    </Link>
                  </motion.li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-4">
        <CoreStatus />
      </div>
    </aside>
  );
}
