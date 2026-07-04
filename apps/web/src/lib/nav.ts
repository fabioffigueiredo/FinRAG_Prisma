import { Gauge, Layers, MessagesSquare, Radar, TriangleAlert, FileText, Upload, ScrollText, type LucideIcon } from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon };
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
];
