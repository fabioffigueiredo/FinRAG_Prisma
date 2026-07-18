"use client";

import { useState, type FormEvent } from "react";
import { ShieldCheck } from "lucide-react";
import { iniciarEnrollment2FA, confirmarEnrollment2FA } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { PasswordInput } from "@/components/ui/password-input";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";

type Etapa = "senha" | "idle" | "qr";

/** Mecânica de enrollment (iniciar → QR → confirmar código real), sem
 * chrome de página — reusado em Meu Perfil (1º cadastro E troca de
 * dispositivo self-service) e na tela obrigatória /ativar-2fa.
 *
 * `exigirSenhaAtual`: quando já existe um 2FA ativo (troca de dispositivo),
 * a API exige a senha atual antes de sobrescrever o segredo (step-up —
 * senão um cookie de sessão roubado sozinho bastaria pra sequestrar o 2FA).
 * Sem isso, entra direto na etapa de QR, mesmo comportamento de sempre. */
export function TotpEnrollment({
  onAtivado,
  exigirSenhaAtual = false,
  onCancelar,
}: {
  onAtivado: () => void;
  exigirSenhaAtual?: boolean;
  onCancelar?: () => void;
}) {
  const [etapa, setEtapa] = useState<Etapa>(exigirSenhaAtual ? "senha" : "idle");
  const [senhaAtual, setSenhaAtual] = useState("");
  const [qrBase64, setQrBase64] = useState<string | null>(null);
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function iniciar(senha?: string) {
    setErro(null);
    setCarregando(true);
    const resultado = await iniciarEnrollment2FA(senha);
    setCarregando(false);
    if (!resultado.ok) {
      setErro(resultado.erro);
      return;
    }
    setQrBase64(resultado.qrBase64);
    setEtapa("qr");
  }

  async function onSubmitSenha(e: FormEvent) {
    e.preventDefault();
    await iniciar(senhaAtual);
  }

  async function confirmar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    const resultado = await confirmarEnrollment2FA(codigo);
    setCarregando(false);
    if (!resultado.ok) {
      setErro(resultado.erro ?? "código inválido");
      return;
    }
    onAtivado();
  }

  if (etapa === "senha") {
    return (
      <form onSubmit={onSubmitSenha} className="space-y-3">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="senha-atual-2fa">Confirme sua senha atual</FieldLabel>
            <PasswordInput
              id="senha-atual-2fa"
              autoComplete="current-password"
              autoFocus
              value={senhaAtual}
              onChange={(e) => setSenhaAtual(e.target.value)}
            />
            <FieldDescription>Pra evitar que uma sessão roubada troque seu 2FA sozinha.</FieldDescription>
          </Field>
          {erro && <p className="text-sm text-destructive">{erro}</p>}
          <div className="flex gap-2">
            <Button type="submit" variant="warning" size="sm" disabled={carregando || !senhaAtual}>
              {carregando ? "Verificando…" : "Continuar"}
            </Button>
            {onCancelar && (
              <Button type="button" variant="ghost" size="sm" onClick={onCancelar}>
                Cancelar
              </Button>
            )}
          </div>
        </FieldGroup>
      </form>
    );
  }

  if (etapa === "idle") {
    return (
      <div className="space-y-2">
        {erro && <p className="text-sm text-destructive">{erro}</p>}
        <Button type="button" variant="outline" size="sm" onClick={() => iniciar()} disabled={carregando}>
          <ShieldCheck className="h-3.5 w-3.5" strokeWidth={1.75} />
          {carregando ? "Gerando…" : "Ativar 2FA"}
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={confirmar} className="space-y-3">
      {qrBase64 && (
        <div className="flex justify-center rounded-lg border border-border bg-card p-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`data:image/png;base64,${qrBase64}`}
            alt="QR code de configuração do 2FA"
            className="h-40 w-40"
          />
        </div>
      )}
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="codigo-2fa">Código do app autenticador</FieldLabel>
          <InputOTP id="codigo-2fa" maxLength={6} value={codigo} onChange={setCodigo}>
            <InputOTPGroup>
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <InputOTPSlot key={i} index={i} />
              ))}
            </InputOTPGroup>
          </InputOTP>
          <FieldDescription>Escaneie o QR acima e digite o código de 6 dígitos gerado.</FieldDescription>
        </Field>
        {erro && <p className="text-sm text-destructive">{erro}</p>}
        <div className="flex gap-2">
          <Button type="submit" variant="warning" size="sm" disabled={carregando || codigo.length < 6}>
            {carregando ? "Confirmando…" : "Confirmar"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              if (exigirSenhaAtual) {
                setEtapa("senha");
              } else {
                setEtapa("idle");
              }
              setQrBase64(null);
              setCodigo("");
              setErro(null);
            }}
          >
            Cancelar
          </Button>
        </div>
      </FieldGroup>
    </form>
  );
}
