import { PrismaMark, PrismaWordmark } from "@/components/brand/logo";
import { PageStagger, Item } from "@/components/app/reveal";
import { CadastroForm } from "./cadastro-form";

/** Split-screen igual ao /login (mesmo momento de marca) — pública de
 * propósito, sem gate de sessão: é a porta de entrada de quem ainda não
 * tem conta. */
function PainelMarca() {
  return (
    <div className="dark relative hidden w-[44%] shrink-0 flex-col justify-between overflow-hidden bg-background px-14 py-12 lg:flex">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(60% 50% at 15% 8%, color-mix(in oklab, var(--primary) 16%, transparent) 0%, transparent 60%)," +
            "radial-gradient(46% 40% at 85% 92%, color-mix(in oklab, var(--primary) 10%, transparent) 0%, transparent 60%)",
        }}
      />
      <PrismaWordmark className="relative" />

      <div className="relative max-w-md space-y-6">
        <p className="font-display text-[2.5rem] leading-[1.08] font-medium tracking-tight text-foreground">
          Peça acesso, um gestor libera.
        </p>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Seu cadastro passa por aprovação antes de virar conta ativa — nenhuma senha trafega por
          e-mail, só um link de ativação de uso único.
        </p>
      </div>

      <div className="relative flex items-center gap-3 text-xs text-muted-foreground/80">
        <PrismaMark className="h-4 w-4 opacity-70" />
        <span className="tabular">Explica, não recomenda.</span>
      </div>
    </div>
  );
}

export default function CadastroPage() {
  return (
    <div className="flex min-h-dvh">
      <PainelMarca />
      <div className="flex flex-1 flex-col items-center justify-center bg-background px-6 py-12">
        <PageStagger className="w-full max-w-sm space-y-8">
          <Item className="lg:hidden">
            <PrismaWordmark />
          </Item>
          <Item className="space-y-1.5">
            <h1 className="font-display text-2xl font-semibold text-foreground">Solicitar acesso</h1>
            <p className="text-sm text-muted-foreground">Preencha seus dados — um gestor aprova o cadastro.</p>
          </Item>
          <Item>
            <CadastroForm />
          </Item>
        </PageStagger>
      </div>
    </div>
  );
}
