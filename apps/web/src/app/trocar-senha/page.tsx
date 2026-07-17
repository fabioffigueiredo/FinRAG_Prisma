import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { PrismaWordmark } from "@/components/brand/logo";
import { PageStagger, Item } from "@/components/app/reveal";
import { TrocarSenhaForm } from "./trocar-senha-form";

const BASE = process.env.NEXT_PUBLIC_PRISMA_API ?? "http://localhost:8000";

/**
 * Gate autoritativo, mesmo padrão de admin/layout.tsx: sem cookie -> /login;
 * sem a flag trocar_senha_no_proximo_login -> / (não deixa escapar via URL
 * quem não precisa trocar). Fora do grupo (app) de propósito — sem
 * sidebar/topbar, e evita o loop de redirect do gate em (app)/layout.tsx.
 */
export default async function TrocarSenhaPage() {
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

  const usuario = (await resp.json()) as { trocar_senha_no_proximo_login: boolean };
  if (!usuario.trocar_senha_no_proximo_login) {
    redirect("/");
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-background px-6 py-12">
      <PageStagger className="w-full max-w-sm space-y-8">
        <Item>
          <PrismaWordmark />
        </Item>
        <Item className="space-y-1.5">
          <h1 className="font-display text-2xl font-semibold text-foreground">Troque sua senha</h1>
          <p className="text-sm text-muted-foreground">
            Sua senha atual é temporária — troque antes de continuar.
          </p>
        </Item>
        <Item>
          <TrocarSenhaForm />
        </Item>
      </PageStagger>
    </div>
  );
}
