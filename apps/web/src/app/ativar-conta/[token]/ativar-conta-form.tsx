"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Check, X } from "lucide-react";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { PasswordInput } from "@/components/ui/password-input";
import { Button } from "@/components/ui/button";
import { getCsrf, ativarConta } from "@/lib/api";
import { checklistSenha, senhaValida } from "@/lib/senha";
import { cn } from "@/lib/utils";

export function AtivarContaForm({ token }: { token: string }) {
  const router = useRouter();
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const regras = checklistSenha(senha);
  const senhasConferem = senha.length > 0 && senha === confirmacao;

  useEffect(() => {
    getCsrf();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    if (!senhaValida(senha)) {
      setErro("a senha não atende à política mínima");
      return;
    }
    if (!senhasConferem) {
      setErro("as senhas não conferem");
      return;
    }
    setEnviando(true);
    const resultado = await ativarConta(token, senha);
    setEnviando(false);
    if (!resultado.ok) {
      setErro(resultado.erro);
      return;
    }
    // /auth/ativar-conta sempre emite sessão completa direto (nunca 2FA em
    // duas etapas — provar a posse do link + escolher a senha já é a prova
    // de identidade dessa etapa); o gate de (app)/layout.tsx cuida de mandar
    // pra /ativar-2fa se o papel exigir 2FA e ainda não estiver configurado.
    router.push("/");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="nova-senha">Escolha uma senha</FieldLabel>
          <PasswordInput
            id="nova-senha"
            autoComplete="new-password"
            autoFocus
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="confirmar-senha">Confirme a senha</FieldLabel>
          <PasswordInput
            id="confirmar-senha"
            autoComplete="new-password"
            value={confirmacao}
            onChange={(e) => setConfirmacao(e.target.value)}
            aria-invalid={confirmacao.length > 0 && !senhasConferem ? true : undefined}
          />
        </Field>
        {senha && (
          <ul className="grid grid-cols-1 gap-1 text-xs sm:grid-cols-2">
            {regras.map((r) => (
              <li
                key={r.label}
                className={cn(
                  "flex items-center gap-1.5",
                  r.ok ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground",
                )}
              >
                {r.ok ? <Check className="h-3 w-3" strokeWidth={2} /> : <X className="h-3 w-3" strokeWidth={1.75} />}
                {r.label}
              </li>
            ))}
          </ul>
        )}
        {erro && <p className="text-sm text-destructive">{erro}</p>}
        <Button
          type="submit"
          variant="warning"
          size="lg"
          disabled={enviando || !senhaValida(senha) || !senhasConferem}
          className="mt-1 w-full"
        >
          {enviando ? "Ativando…" : "Ativar conta e entrar"}
        </Button>
      </FieldGroup>
    </form>
  );
}
