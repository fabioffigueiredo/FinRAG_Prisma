"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { PrismaWordmark, PrismaMark } from "@/components/brand/logo";
import { CoreStatus } from "@/components/app/core-status";
import { navParaPapel } from "@/lib/nav";
import { useSession } from "@/components/app/session-context";
import { cn } from "@/lib/utils";
import { easeOutQuint } from "@/lib/motion";

const STORE_KEY = "prisma:sidebar-collapsed";

export function Sidebar() {
  const path = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { usuario } = useSession();
  const nav = navParaPapel(usuario?.papel);

  // estado persistido (lido no cliente p/ evitar mismatch de hidratação)
  useEffect(() => {
    setCollapsed(localStorage.getItem(STORE_KEY) === "1");
  }, []);
  const toggle = () => {
    setCollapsed((v) => {
      const nv = !v;
      localStorage.setItem(STORE_KEY, nv ? "1" : "0");
      return nv;
    });
  };

  let idx = 0;
  return (
    <aside
      data-collapsed={collapsed}
      className={cn(
        "hidden shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-300 md:flex print:!hidden",
        collapsed ? "w-[72px]" : "w-[248px]",
      )}
      style={{ transitionTimingFunction: "var(--ease-out-quint)" }}
    >
      <div className={cn("flex h-16 items-center gap-2", collapsed ? "justify-center px-0" : "px-4")}>
        {!collapsed && (
          <Link href="/" aria-label="Prisma — início" className="mr-auto transition-opacity hover:opacity-80">
            <PrismaWordmark />
          </Link>
        )}
        <button
          onClick={toggle}
          aria-label={collapsed ? "Expandir menu" : "Recolher menu"}
          aria-expanded={!collapsed}
          title={collapsed ? "Expandir menu" : "Recolher menu"}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-sidebar-accent/60 hover:text-foreground"
        >
          {collapsed ? (
            <PanelLeftOpen className="h-[19px] w-[19px]" strokeWidth={1.75} />
          ) : (
            <PanelLeftClose className="h-[19px] w-[19px]" strokeWidth={1.75} />
          )}
        </button>
      </div>

      <nav className="flex-1 space-y-6 px-3 py-4">
        {nav.map((sec) => (
          <div key={sec.grupo}>
            <p
              className={cn(
                "px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/70 transition-opacity",
                collapsed && "pointer-events-none h-0 select-none overflow-hidden pb-0 opacity-0",
              )}
            >
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
                      title={collapsed ? item.label : undefined}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-lg py-2 text-sm transition-colors duration-200",
                        collapsed ? "justify-center px-0" : "px-3",
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
                      <span className={cn("truncate", collapsed && "hidden")}>{item.label}</span>
                    </Link>
                  </motion.li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className={cn("border-t border-sidebar-border", collapsed ? "flex justify-center p-3" : "p-4")}>
        <CoreStatus collapsed={collapsed} />
      </div>
    </aside>
  );
}
