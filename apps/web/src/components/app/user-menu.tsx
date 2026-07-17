"use client";

import Link from "next/link";
import { LogOut, User } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useSession } from "@/components/app/session-context";
import { iniciaisNome } from "@/lib/utils";

const BASE = process.env.NEXT_PUBLIC_PRISMA_API ?? "http://localhost:8000";

export function UserMenu() {
  const { usuario, logout } = useSession();

  if (!usuario) return null;

  const avatarSrc = usuario.avatar_url ? `${BASE}${usuario.avatar_url}` : undefined;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            aria-label="Menu do usuário"
            className="flex items-center gap-2 rounded-lg border border-border bg-card p-1 transition-colors hover:border-primary/40"
          />
        }
      >
        <Avatar size="sm">
          {avatarSrc && <AvatarImage src={avatarSrc} alt={usuario.nome} />}
          <AvatarFallback>{iniciaisNome(usuario.nome)}</AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex flex-col gap-0.5 px-1.5 py-1.5">
            <span className="truncate text-sm font-medium text-foreground">{usuario.nome}</span>
            <span className="font-mono text-[11px] text-muted-foreground">{usuario.matricula}</span>
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem render={<Link href="/perfil" />}>
          <User />
          Meu Perfil
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={() => logout()}>
          <LogOut />
          Sair
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
