"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, CheckCircle2, Database, LockKeyhole, Route } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PrismaMark, PrismaWordmark } from "@/components/brand/logo";

const BASE = process.env.NEXT_PUBLIC_PRISMA_API ?? "http://localhost:8000";

type DemoStatus = {
  dados: string;
  texto: { estado: string; motor: string };
  embeddings: { estado: string; motor: string };
  radar: { estado?: string; atualizado_em?: string | null; motivo?: string | null };
};

const estadoHumano: Record<string, string> = {
  disponivel: "disponível",
  degradado: "degradado",
  indisponivel: "indisponível",
};

export default function DemonstracaoPage() {
  const [status, setStatus] = useState<DemoStatus | null>(null);

  useEffect(() => {
    fetch(`${BASE}/demo/status`)
      .then((response) => (response.ok ? response.json() : null))
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  return (
    <main className="min-h-dvh bg-background px-5 py-6 text-foreground md:px-10 md:py-10">
      <div className="mx-auto max-w-6xl">
        <header className="flex items-center justify-between border-b border-border pb-5">
          <PrismaWordmark />
          <Link href="/login" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Já tenho acesso
          </Link>
        </header>

        <section className="grid gap-10 py-14 lg:grid-cols-[1.15fr_0.85fr] lg:items-end">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-primary">Demonstração pública · cenário fictício</p>
            <h1 className="mt-5 max-w-3xl font-display text-5xl font-medium leading-[0.96] tracking-tight md:text-7xl">
              Uma explicação só vale quando o caminho fica visível.
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground md:text-lg">
              Esta rota apresenta um cenário fixo do PRISMA: atribuição, fontes e limites. Não cria sessão,
              não recebe documentos e não produz recomendação financeira.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" nativeButton={false} variant="warning" render={<Link href="#cenario" />}>
                Ver o cenário <ArrowUpRight className="h-4 w-4" />
              </Button>
              <Button size="lg" nativeButton={false} variant="outline" render={<Link href="/cadastro" />}>
                Solicitar acesso
              </Button>
            </div>
          </div>
          <aside className="border-l-2 border-primary bg-card p-6 shadow-sm">
            <p className="font-mono text-xs uppercase tracking-[0.14em] text-primary">Estado do ambiente</p>
            <dl className="mt-5 space-y-4 text-sm">
              <div className="flex items-start justify-between gap-5 border-b border-border pb-3"><dt className="text-muted-foreground">Dados</dt><dd className="font-medium">{status?.dados ?? "verificando"}</dd></div>
              <div className="flex items-start justify-between gap-5 border-b border-border pb-3"><dt className="text-muted-foreground">Texto</dt><dd className="text-right font-medium">{status ? `${status.texto.motor} · ${estadoHumano[status.texto.estado] ?? status.texto.estado}` : "verificando"}</dd></div>
              <div className="flex items-start justify-between gap-5 border-b border-border pb-3"><dt className="text-muted-foreground">Embeddings</dt><dd className="text-right font-medium">{status ? `${status.embeddings.motor} · ${estadoHumano[status.embeddings.estado] ?? status.embeddings.estado}` : "verificando"}</dd></div>
              <div className="flex items-start justify-between gap-5"><dt className="text-muted-foreground">Radar</dt><dd className="text-right font-medium">{status ? estadoHumano[status.radar.estado ?? "indisponivel"] ?? status.radar.estado : "verificando"}</dd></div>
            </dl>
          </aside>
        </section>

        <section id="cenario" className="border-y border-border py-10">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-primary">Cenário demonstrado</p>
          <div className="mt-5 grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
            <div className="bg-[linear-gradient(135deg,color-mix(in_oklab,var(--primary)_12%,transparent),transparent_46%)] p-7 ring-1 ring-border md:p-9">
              <p className="text-sm text-muted-foreground">Pergunta fixa</p>
              <p className="mt-2 font-display text-2xl leading-tight md:text-3xl">“Quais estratégias explicaram o excesso de retorno no período?”</p>
              <div className="mt-8 grid gap-3 sm:grid-cols-3">
                {["Fontes recuperadas", "Motor registrado", "Hash da consulta"].map((item) => (
                  <div key={item} className="border border-border bg-background/75 p-4 text-sm font-medium">{item}</div>
                ))}
              </div>
              <p className="mt-7 text-sm leading-6 text-muted-foreground">O conteúdo exposto aqui é fictício e foi escolhido para demonstrar a estrutura de uma resposta revisável. Não representa carteira, cliente ou resultado real.</p>
            </div>
            <div className="space-y-3">
              {[
                [Route, "1. Explore", "Confira o cenário público, sem cadastro."],
                [LockKeyhole, "2. Solicite acesso", "Preencha o cadastro. Uma pessoa gestora ou de compliance avalia a solicitação."],
                [CheckCircle2, "3. Ative a conta", "Após aprovação, defina a senha. Perfis de gestor e compliance configuram 2FA."],
              ].map(([Icon, title, body]) => {
                const ItemIcon = Icon as typeof Route;
                return <article key={title as string} className="flex gap-4 border border-border p-4"><ItemIcon className="mt-0.5 h-5 w-5 shrink-0 text-primary" /><div><h2 className="font-medium">{title as string}</h2><p className="mt-1 text-sm leading-5 text-muted-foreground">{body as string}</p></div></article>;
              })}
            </div>
          </div>
        </section>

        <footer className="flex flex-col gap-3 py-7 text-sm text-muted-foreground md:flex-row md:items-center md:justify-between">
          <span className="flex items-center gap-2"><PrismaMark className="h-4 w-4" />Explica, não recomenda.</span>
          <span className="flex items-center gap-2"><Database className="h-4 w-4" />Dados e limites visíveis antes de qualquer interpretação.</span>
        </footer>
      </div>
    </main>
  );
}
