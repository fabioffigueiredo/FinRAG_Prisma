import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { PrismaWordmark } from "@/components/brand/logo";
import { PageStagger, Item } from "@/components/app/reveal";
import { AtivarDoisFatoresShell } from "./ativar-2fa-shell";

const BASE = process.env.NEXT_PUBLIC_PRISMA_API ?? "http://localhost:8000";

/**
 * Gate autoritativo: sem cookie -> /login; papel errado ou 2FA já ativado
 * -> / (não deixa escapar via URL quem não precisa configurar). Fora do
 * grupo (app) de propósito — sem sidebar/topbar, evita loop de redirect.
 */
export default async function AtivarDoisFatoresPage() {
  const cookieStore = await cookies();
  const sessao = cookieStore.get("prisma_session")?.value;

  if (!sessao) {
    redirect("/login");
  }

  const resp = await fetch(`${BASE}/auth/me`, {
    headers: { cookie: `prisma_session=${sessao}` },
    cache: "no-store",
  });

  if (!resp.ok) {
    redirect("/login");
  }

  const usuario = (await resp.json()) as { papel: string; totp_ativado: boolean };
  if ((usuario.papel !== "gestor" && usuario.papel !== "compliance") || usuario.totp_ativado) {
    redirect("/");
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-background px-6 py-12">
      <PageStagger className="w-full max-w-sm space-y-8">
        <Item>
          <PrismaWordmark />
        </Item>
        <Item className="space-y-1.5">
          <h1 className="font-display text-2xl font-semibold text-foreground">Ative a autenticação em duas etapas</h1>
          <p className="text-sm text-muted-foreground">
            Obrigatório para gestor/compliance — configure com Google Authenticator, Microsoft Authenticator ou
            similar antes de continuar.
          </p>
        </Item>
        <Item>
          <AtivarDoisFatoresShell />
        </Item>
      </PageStagger>
    </div>
  );
}
