"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { navParaPapel } from "@/lib/nav";
import { useSession } from "@/components/app/session-context";

/** Cmd+K — caminho paralelo à sidebar (padrão Linear), sempre com os mesmos
 * itens já filtrados por papel. */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { usuario } = useSession();
  const nav = navParaPapel(usuario?.papel);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  function ir(href: string) {
    setOpen(false);
    router.push(href);
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="Navegação" description="Ir para uma tela do Prisma">
      <Command>
        <CommandInput placeholder="Ir para…" />
        <CommandList>
          <CommandEmpty>Nada encontrado.</CommandEmpty>
          {nav.map((grupo) => (
            <CommandGroup key={grupo.grupo} heading={grupo.grupo}>
              {grupo.itens.map((item) => (
                <CommandItem key={item.href} value={item.label} onSelect={() => ir(item.href)}>
                  <item.icon strokeWidth={1.75} />
                  {item.label}
                </CommandItem>
              ))}
            </CommandGroup>
          ))}
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
