import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Sidebar } from "@/components/app/sidebar";
import { Topbar } from "@/components/app/topbar";
import { MobileTabBar } from "@/components/app/mobile-tabbar";
import { BackendProvider } from "@/components/app/backend-context";
import { FundProvider } from "@/components/app/fund-context";
import { MotionProvider } from "@/components/app/motion-provider";
import { SessionProvider } from "@/components/app/session-context";
import { CommandPalette } from "@/components/app/command-palette";
import { Toaster } from "@/components/ui/sonner";

const BASE = process.env.NEXT_PUBLIC_PRISMA_API ?? "http://localhost:8000";

/**
 * Ponto de verdade das telas obrigatórias — checa NESTA ORDEM: 1) senha
 * temporária (trocar_senha_no_proximo_login) primeiro, sempre, antes de
 * qualquer outra coisa, inclusive configurar 2FA; 2) só depois, gestor/
 * compliance sem 2FA ativado. /trocar-senha e /ativar-2fa ficam fora deste
 * grupo de propósito (sem sidebar/topbar, evita loop de redirect).
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const sessao = cookieStore.get("prisma_session")?.value;

  if (sessao) {
    const resp = await fetch(`${BASE}/auth/me`, {
      headers: { cookie: `prisma_session=${sessao}` },
      cache: "no-store",
    });
    if (resp.ok) {
      const usuario = (await resp.json()) as {
        papel: string;
        totp_ativado: boolean;
        trocar_senha_no_proximo_login: boolean;
      };
      if (usuario.trocar_senha_no_proximo_login) {
        redirect("/trocar-senha");
      }
      if ((usuario.papel === "gestor" || usuario.papel === "compliance") && !usuario.totp_ativado) {
        redirect("/ativar-2fa");
      }
    }
  }

  return (
    <MotionProvider>
      <SessionProvider>
        <BackendProvider>
          <FundProvider>
            <div className="flex min-h-dvh">
              <Sidebar />
              <div className="flex min-w-0 flex-1 flex-col">
                <Topbar />
                <main className="flex-1 px-4 py-6 pb-24 md:px-8 md:py-8 md:pb-8">{children}</main>
              </div>
            </div>
            <MobileTabBar />
            <CommandPalette />
            <Toaster />
          </FundProvider>
        </BackendProvider>
      </SessionProvider>
    </MotionProvider>
  );
}
