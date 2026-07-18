import Link from "next/link";
import { PrismaWordmark } from "@/components/brand/logo";
import { PageStagger, Item } from "@/components/app/reveal";
import { Button } from "@/components/ui/button";
import { AtivarContaForm } from "./ativar-conta-form";

const BASE = process.env.NEXT_PUBLIC_PRISMA_API ?? "http://localhost:8000";

/** Gate no servidor, mesmo padrão de trocar-senha/page.tsx: valida o token
 * ANTES de renderizar o formulário — nunca mostra o form pra um link
 * expirado/já usado/inexistente. */
export default async function AtivarContaPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const resp = await fetch(`${BASE}/auth/convite/${encodeURIComponent(token)}`, { cache: "no-store" });

  if (!resp.ok) {
    const corpo = await resp.json().catch(() => ({}));
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center bg-background px-6 py-12">
        <PageStagger className="w-full max-w-sm space-y-6 text-center">
          <Item>
            <PrismaWordmark className="mx-auto" />
          </Item>
          <Item className="space-y-1.5">
            <h1 className="font-display text-2xl font-semibold text-foreground">Link inválido</h1>
            <p className="text-sm text-muted-foreground">
              {corpo.detail ?? "Este link de ativação não é mais válido — peça um novo convite a um gestor."}
            </p>
          </Item>
          <Item>
            <Button variant="outline" size="sm" render={<Link href="/login" />}>
              Voltar para o login
            </Button>
          </Item>
        </PageStagger>
      </div>
    );
  }

  const dados = (await resp.json()) as { nome: string; matricula: string };

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-background px-6 py-12">
      <PageStagger className="w-full max-w-sm space-y-8">
        <Item>
          <PrismaWordmark />
        </Item>
        <Item className="space-y-1.5">
          <h1 className="font-display text-2xl font-semibold text-foreground">Bem-vindo(a), {dados.nome}</h1>
          <p className="text-sm text-muted-foreground">
            Defina sua senha pra ativar a conta <span className="font-mono">{dados.matricula}</span>.
          </p>
        </Item>
        <Item>
          <AtivarContaForm token={token} />
        </Item>
      </PageStagger>
    </div>
  );
}
