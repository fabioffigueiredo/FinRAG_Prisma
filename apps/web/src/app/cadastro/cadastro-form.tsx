"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { getCsrf, solicitarCadastro } from "@/lib/api";

export function CadastroForm() {
  const [matricula, setMatricula] = useState("");
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [telefone, setTelefone] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState(false);

  useEffect(() => {
    getCsrf();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    const resultado = await solicitarCadastro({
      matricula,
      nome,
      email,
      telefone: telefone || undefined,
    });
    setEnviando(false);
    if (!resultado.ok) {
      setErro(resultado.erro ?? "não foi possível enviar o cadastro");
      return;
    }
    setEnviado(true);
  }

  if (enviado) {
    return (
      <div className="space-y-4 text-center">
        <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-600 dark:text-emerald-400" strokeWidth={1.5} />
        <div className="space-y-1.5">
          <h2 className="font-display text-lg font-semibold text-foreground">Pedido enviado</h2>
          <p className="text-sm text-muted-foreground">
            Um gestor vai analisar seu cadastro. Quando for aprovado, você recebe um e-mail com o link pra
            definir sua senha e ativar a conta.
          </p>
        </div>
        <Button variant="outline" size="sm" render={<Link href="/login" />}>
          Voltar para o login
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <FieldGroup>
        {erro && <p className="text-sm text-destructive">{erro}</p>}
        <Field data-invalid={erro ? true : undefined}>
          <FieldLabel htmlFor="matricula">Matrícula</FieldLabel>
          <Input
            id="matricula"
            autoFocus
            value={matricula}
            onChange={(e) => setMatricula(e.target.value)}
            required
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="nome">Nome completo</FieldLabel>
          <Input id="nome" value={nome} onChange={(e) => setNome(e.target.value)} required />
        </Field>
        <Field>
          <FieldLabel htmlFor="email">E-mail</FieldLabel>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="telefone">Telefone (opcional)</FieldLabel>
          <Input id="telefone" value={telefone} onChange={(e) => setTelefone(e.target.value)} />
        </Field>
        <Button
          type="submit"
          variant="warning"
          size="lg"
          disabled={enviando || !matricula || !nome || !email}
          className="mt-1 w-full"
        >
          {enviando ? "Enviando…" : "Solicitar cadastro"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Já tem conta?{" "}
          <Link href="/login" className="font-medium text-foreground underline underline-offset-2">
            Entrar
          </Link>
        </p>
      </FieldGroup>
    </form>
  );
}
