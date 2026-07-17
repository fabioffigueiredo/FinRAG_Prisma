import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const BASE = process.env.NEXT_PUBLIC_PRISMA_API ?? "http://localhost:8000";

/**
 * Gate autoritativo da sub-árvore /admin — diferente do middleware (que só
 * checa presença do cookie), este Server Component confirma o PAPEL de
 * verdade no backend antes de renderizar. Nunca decodifica o JWT no
 * cliente pra essa decisão (o cookie de sessão é httpOnly mesmo).
 */
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const sessao = cookieStore.get("prisma_session")?.value;

  if (!sessao) {
    redirect("/login?from=/admin");
  }

  const resp = await fetch(`${BASE}/auth/me`, {
    headers: { cookie: `prisma_session=${sessao}` },
    cache: "no-store",
  });

  if (!resp.ok) {
    redirect("/login?from=/admin");
  }

  const usuario = (await resp.json()) as { papel: string };
  if (usuario.papel !== "gestor" && usuario.papel !== "compliance") {
    redirect("/");
  }

  return <>{children}</>;
}
