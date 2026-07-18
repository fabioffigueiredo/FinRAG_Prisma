"use client";

import { Suspense, useEffect, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { PrismaMark, PrismaWordmark } from "@/components/brand/logo";
import { Field, FieldGroup, FieldLabel, FieldError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Button } from "@/components/ui/button";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { getCsrf, login, loginMicrosoftDemo, verificar2fa } from "@/lib/api";
import { PageStagger, Item } from "@/components/app/reveal";

type EtapaLogin = "credenciais" | "2fa";

/** Glifo oficial de 4 cores — nunca decorativo fora deste contexto. */
function MicrosoftGlyph() {
  return (
    <svg viewBox="0 0 21 21" className="h-4 w-4" aria-hidden="true">
      <rect x="1" y="1" width="9" height="9" fill="#f25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
      <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
      <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
    </svg>
  );
}

/**
 * Split-screen: painel esquerdo é SEMPRE escuro (momento de marca, ancorado
 * pela classe `.dark` local — independe do tema escolhido pelo usuário, o
 * mesmo truque editorial de Stripe/Vercel), painel direito segue o tema real.
 */
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
          A atribuição de performance, explicada.
        </p>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Narrativa gerada sobre números que já existem, com citação às fontes e
          trilha de auditoria — pensado para um ambiente regulado, nunca para
          recomendar.
        </p>
      </div>

      <div className="relative flex items-center gap-3 text-xs text-muted-foreground/80">
        <PrismaMark className="h-4 w-4 opacity-70" />
        <span className="tabular">Explica, não recomenda.</span>
      </div>
    </div>
  );
}

function Codigo2FAForm({ destino }: { destino: string }) {
  const router = useRouter();
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    const resultado = await verificar2fa(codigo);
    setEnviando(false);
    if (!resultado.ok) {
      // Mesmo erro genérico da etapa de senha — não confirma se o código
      // chegou perto de estar certo (ASVS: nada de feedback granular aqui).
      setErro(resultado.erro);
      return;
    }
    router.push(destino);
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <FieldGroup>
        <Field data-invalid={erro ? true : undefined}>
          <FieldLabel htmlFor="codigo-2fa-login">Código do app autenticador</FieldLabel>
          <InputOTP id="codigo-2fa-login" maxLength={6} value={codigo} onChange={setCodigo} autoFocus>
            <InputOTPGroup>
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <InputOTPSlot key={i} index={i} />
              ))}
            </InputOTPGroup>
          </InputOTP>
          {erro && <FieldError>{erro}</FieldError>}
        </Field>
        <Button
          type="submit"
          variant="warning"
          size="lg"
          disabled={enviando || codigo.length < 6}
          className="mt-1 w-full"
        >
          {enviando ? "Verificando…" : "Verificar"}
        </Button>
      </FieldGroup>
    </form>
  );
}

function CredenciaisForm({
  destino,
  onRequer2FA,
}: {
  destino: string;
  onRequer2FA: () => void;
}) {
  const router = useRouter();
  const [matricula, setMatricula] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [enviandoMs, setEnviandoMs] = useState(false);

  useEffect(() => {
    getCsrf();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    const resultado = await login(matricula, senha);
    setEnviando(false);
    if (!resultado.ok) {
      setErro(resultado.erro);
      return;
    }
    if (resultado.requer2fa) {
      onRequer2FA();
      return;
    }
    router.push(destino);
    router.refresh();
  }

  /** Simulação de demo — não é OAuth/OIDC real, não fala com Azure AD, e
   * sempre loga a mesma conta demo fixa (ver services/prisma-api/app.py::
   * login_microsoft_demo). Um clique só, propositalmente nunca aciona 2FA
   * (a conta demo é sempre analista). */
  async function onMicrosoftDemo() {
    setErro(null);
    setEnviandoMs(true);
    const resultado = await loginMicrosoftDemo();
    setEnviandoMs(false);
    if (!resultado.ok) {
      setErro(resultado.erro);
      return;
    }
    router.push(destino);
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <FieldGroup>
        <Field data-invalid={erro ? true : undefined}>
          <FieldLabel htmlFor="matricula">Matrícula</FieldLabel>
          <Input
            id="matricula"
            name="matricula"
            autoComplete="username"
            autoFocus
            value={matricula}
            onChange={(e) => setMatricula(e.target.value)}
            aria-invalid={erro ? true : undefined}
          />
        </Field>
        <Field data-invalid={erro ? true : undefined}>
          <FieldLabel htmlFor="senha">Senha</FieldLabel>
          <PasswordInput
            id="senha"
            name="senha"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            aria-invalid={erro ? true : undefined}
          />
          {erro && <FieldError>{erro}</FieldError>}
        </Field>
        <Button
          type="submit"
          variant="warning"
          size="lg"
          disabled={enviando || !matricula || !senha}
          className="mt-1 w-full"
        >
          {enviando ? "Entrando…" : "Entrar"}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="lg"
          onClick={onMicrosoftDemo}
          disabled={enviandoMs}
          className="w-full"
        >
          <MicrosoftGlyph />
          {enviandoMs ? "Entrando…" : "Entrar com Microsoft"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Não tem conta?{" "}
          <Link href="/cadastro" className="font-medium text-foreground underline underline-offset-2">
            Cadastre-se
          </Link>
        </p>
      </FieldGroup>
    </form>
  );
}

function LoginForm({
  etapa,
  setEtapa,
  destino,
}: {
  etapa: EtapaLogin;
  setEtapa: Dispatch<SetStateAction<EtapaLogin>>;
  destino: string;
}) {
  if (etapa === "2fa") {
    return <Codigo2FAForm destino={destino} />;
  }
  return <CredenciaisForm destino={destino} onRequer2FA={() => setEtapa("2fa")} />;
}

function LoginContent() {
  const searchParams = useSearchParams();
  const destino = searchParams.get("from") ?? "/";
  const [etapa, setEtapa] = useState<EtapaLogin>("credenciais");

  return (
    <div className="flex min-h-dvh">
      <PainelMarca />
      <div className="flex flex-1 flex-col items-center justify-center bg-background px-6 py-12">
        <PageStagger className="w-full max-w-sm space-y-8">
          <Item className="lg:hidden">
            <PrismaWordmark />
          </Item>
          <Item className="space-y-1.5">
            {etapa === "2fa" ? (
              <>
                <h1 className="font-display text-2xl font-semibold text-foreground">Verificação em duas etapas</h1>
                <p className="text-sm text-muted-foreground">Digite o código do seu app autenticador.</p>
              </>
            ) : (
              <>
                <h1 className="font-display text-2xl font-semibold text-foreground">Entrar</h1>
                <p className="text-sm text-muted-foreground">Acesse o Prisma com sua matrícula.</p>
              </>
            )}
          </Item>
          <Item>
            <LoginForm etapa={etapa} setEtapa={setEtapa} destino={destino} />
          </Item>
        </PageStagger>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginContent />
    </Suspense>
  );
}
