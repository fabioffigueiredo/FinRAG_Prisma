"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { cn } from "@/lib/utils";

/** Toggle claro/escuro em pílula (sol · lua), no padrão do design Stitch. */
export function ThemeToggle() {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const dark = resolvedTheme === "dark";

  return (
    <div
      role="group"
      aria-label="Tema"
      className="flex items-center gap-0.5 rounded-full border border-border bg-muted/40 p-0.5"
    >
      {[
        { id: "light", icon: Sun, on: mounted && !dark, label: "Tema claro" },
        { id: "dark", icon: Moon, on: mounted && dark, label: "Tema escuro" },
      ].map(({ id, icon: Icon, on, label }) => (
        <button
          key={id}
          onClick={() => setTheme(id)}
          aria-pressed={on}
          aria-label={label}
          title={label}
          className={cn(
            "flex h-7 w-8 items-center justify-center rounded-full transition-colors duration-200",
            on
              ? "bg-card text-primary shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Icon className="h-[15px] w-[15px]" strokeWidth={2} />
        </button>
      ))}
    </div>
  );
}
