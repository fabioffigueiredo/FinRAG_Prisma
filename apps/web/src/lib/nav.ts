import { Gauge, Layers, MessagesSquare, Radar, TriangleAlert, FileText, Upload, ScrollText, Users, type LucideIcon } from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Papéis que veem este item — omitido = visível pra todos. */
  roles?: string[];
};
export type NavGroup = { grupo: string; itens: NavItem[] };

/** Navegação canônica — compartilhada entre Sidebar (desktop) e MobileNav (Sheet). */
export const NAV: NavGroup[] = [
  {
    grupo: "Análise",
    itens: [
      { href: "/", label: "Cockpit", icon: Gauge },
      { href: "/atribuicao", label: "Atribuição", icon: Layers },
      { href: "/copiloto", label: "Pergunte ao Prisma", icon: MessagesSquare },
      { href: "/radar", label: "Radar de Mercado", icon: Radar },
      { href: "/sinais", label: "Sinais", icon: TriangleAlert },
    ],
  },
  {
    grupo: "Saídas",
    itens: [
      { href: "/relatorio", label: "Relatório", icon: FileText },
      { href: "/auditoria", label: "Auditoria", icon: ScrollText },
      { href: "/standalone", label: "Modo standalone", icon: Upload },
    ],
  },
  {
    grupo: "Administração",
    itens: [
      { href: "/admin/usuarios", label: "Usuários", icon: Users, roles: ["gestor", "compliance"] },
    ],
  },
];

/** Filtra a navegação pelo papel da sessão — some grupos que ficam vazios. */
export function navParaPapel(papel: string | undefined | null): NavGroup[] {
  return NAV.map((grupo) => ({
    ...grupo,
    itens: grupo.itens.filter((item) => !item.roles || (papel != null && item.roles.includes(papel))),
  })).filter((grupo) => grupo.itens.length > 0);
}
