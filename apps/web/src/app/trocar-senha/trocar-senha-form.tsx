"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { trocarSenha } from "@/lib/api";
import { checklistSenha, senhaValida } from "@/lib/senha";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Check, X } from "lucide-react";

export function TrocarSenhaForm() {
  const router = useRouter();
  const [senhaAtual, setSenhaAtual] = useState("");
  const [senhaNova, setSenhaNova] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const regras = checklistSenha(senhaNova);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    if (!senhaValida(senhaNova)) {
      setErro("a nova senha não atende à política mínima");
      return;
    }
    setEnviando(true);
    const resultado = await trocarSenha(senhaAtual, senhaNova);
    setEnviando(false);
    if (!resultado.ok) {
      setErro(resultado.erro ?? "não foi possível trocar a senha");
      return;
    }
    router.push("/");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <FieldGroup>
        <Field data-invalid={erro ? true : undefined}>
          <FieldLabel htmlFor="senha-atual">Senha atual (temporária)</FieldLabel>
          <Input
            id="senha-atual"
            type="password"
            autoComplete="current-password"
            autoFocus
            value={senhaAtual}
            onChange={(e) => setSenhaAtual(e.target.value)}
            aria-invalid={erro ? true : undefined}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="senha-nova">Nova senha</FieldLabel>
          <Input
            id="senha-nova"
            type="password"
            autoComplete="new-password"
            value={senhaNova}
            onChange={(e) => setSenhaNova(e.target.value)}
          />
        </Field>
        {senhaNova && (
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
          disabled={enviando || !senhaAtual || !senhaValida(senhaNova)}
          className="mt-1 w-full"
        >
          {enviando ? "Salvando…" : "Trocar senha e continuar"}
        </Button>
      </FieldGroup>
    </form>
  );
}
