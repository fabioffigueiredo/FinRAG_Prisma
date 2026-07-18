"use client";

import { useRef, useState, type FormEvent } from "react";
import { Camera, Check, KeyRound, RefreshCcw, ShieldCheck, ShieldOff, X } from "lucide-react";
import { toast } from "sonner";
import { uploadAvatar, trocarSenha } from "@/lib/api";
import { checklistSenha, senhaValida } from "@/lib/senha";
import { useSession } from "@/components/app/session-context";
import { PageStagger, Item } from "@/components/app/reveal";
import { TotpEnrollment } from "@/components/app/totp-enrollment";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { PasswordInput } from "@/components/ui/password-input";
import { cn, iniciaisNome } from "@/lib/utils";

const BASE = process.env.NEXT_PUBLIC_PRISMA_API ?? "http://localhost:8000";

function SecaoAvatar() {
  const { usuario, refresh } = useSession();
  const inputRef = useRef<HTMLInputElement>(null);
  const [enviando, setEnviando] = useState(false);

  if (!usuario) return null;
  const avatarSrc = usuario.avatar_url ? `${BASE}${usuario.avatar_url}` : undefined;

  async function onArquivoSelecionado(e: React.ChangeEvent<HTMLInputElement>) {
    const arquivo = e.target.files?.[0];
    e.target.value = "";
    if (!arquivo) return;
    setEnviando(true);
    const resultado = await uploadAvatar(arquivo);
    setEnviando(false);
    if (!resultado.ok) {
      toast.error(resultado.erro ?? "não foi possível enviar a foto");
      return;
    }
    await refresh();
    toast.success("Foto atualizada.");
  }

  return (
    <Item className="card-surface space-y-4 p-5">
      <div>
        <h2 className="text-sm font-semibold text-foreground">Foto de perfil</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">JPEG, PNG ou WEBP — até 2MB.</p>
      </div>
      <div className="flex items-center gap-4">
        <Avatar size="lg">
          {avatarSrc && <AvatarImage src={avatarSrc} alt={usuario.nome} />}
          <AvatarFallback>{iniciaisNome(usuario.nome)}</AvatarFallback>
        </Avatar>
        <div className="space-y-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={enviando}
            onClick={() => inputRef.current?.click()}
          >
            <Camera className="h-3.5 w-3.5" strokeWidth={1.75} />
            {enviando ? "Enviando…" : "Trocar foto"}
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={onArquivoSelecionado}
          />
        </div>
      </div>
    </Item>
  );
}

function Secao2FA() {
  const { usuario, refresh } = useSession();
  const [trocando, setTrocando] = useState(false);

  if (!usuario || (usuario.papel !== "gestor" && usuario.papel !== "compliance")) return null;

  async function onAtivado() {
    toast.success(trocando ? "Dispositivo trocado — 2FA reconfigurado." : "2FA ativado.");
    setTrocando(false);
    await refresh();
  }

  return (
    <Item className="card-surface space-y-4 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Autenticação em duas etapas</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Obrigatório para gestor/compliance — Google Authenticator, Microsoft Authenticator ou similar.
          </p>
        </div>
        {usuario.totp_ativado ? (
          <Badge variant="secondary" className="shrink-0 gap-1">
            <ShieldCheck className="h-3 w-3" strokeWidth={2} /> Ativo
          </Badge>
        ) : (
          <Badge variant="outline" className="shrink-0 gap-1 text-muted-foreground">
            <ShieldOff className="h-3 w-3" strokeWidth={1.75} /> Não configurado
          </Badge>
        )}
      </div>

      {usuario.totp_ativado && !trocando ? (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Já configurado nesta conta. Trocando de celular? Confirme sua senha atual pra migrar de dispositivo.
            Perdeu o acesso por completo (sem senha e sem o app antigo)? Peça a um gestor/compliance pra
            resetar o seu 2FA.
          </p>
          <Button type="button" variant="outline" size="sm" onClick={() => setTrocando(true)}>
            <RefreshCcw className="h-3.5 w-3.5" strokeWidth={1.75} />
            Trocar de dispositivo
          </Button>
        </div>
      ) : (
        <TotpEnrollment
          onAtivado={onAtivado}
          exigirSenhaAtual={usuario.totp_ativado}
          onCancelar={trocando ? () => setTrocando(false) : undefined}
        />
      )}
    </Item>
  );
}

function SecaoSenha() {
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
    toast.success("Senha alterada.");
    setSenhaAtual("");
    setSenhaNova("");
  }

  return (
    <Item className="card-surface space-y-4 p-5">
      <div>
        <h2 className="text-sm font-semibold text-foreground">Senha</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">Padrão de instituição financeira — mínimo de 10 caracteres.</p>
      </div>
      <form onSubmit={onSubmit}>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="senha-atual">Senha atual</FieldLabel>
            <PasswordInput
              id="senha-atual"
              value={senhaAtual}
              onChange={(e) => setSenhaAtual(e.target.value)}
              required
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="senha-nova">Nova senha</FieldLabel>
            <PasswordInput
              id="senha-nova"
              value={senhaNova}
              onChange={(e) => setSenhaNova(e.target.value)}
              required
            />
          </Field>
          {senhaNova && (
            <ul className="grid grid-cols-1 gap-1 text-xs sm:grid-cols-2">
              {regras.map((r) => (
                <li
                  key={r.label}
                  className={cn("flex items-center gap-1.5", r.ok ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground")}
                >
                  {r.ok ? <Check className="h-3 w-3" strokeWidth={2} /> : <X className="h-3 w-3" strokeWidth={1.75} />}
                  {r.label}
                </li>
              ))}
            </ul>
          )}
          {erro && <p className="text-sm text-destructive">{erro}</p>}
          <div>
            <Button type="submit" variant="warning" size="sm" disabled={enviando}>
              <KeyRound className="h-3.5 w-3.5" strokeWidth={1.75} />
              {enviando ? "Salvando…" : "Trocar senha"}
            </Button>
          </div>
        </FieldGroup>
      </form>
    </Item>
  );
}

export default function PerfilPage() {
  const { usuario } = useSession();

  return (
    <PageStagger className="mx-auto max-w-2xl space-y-6">
      <Item>
        <h1 className="font-display text-2xl font-semibold text-foreground">Meu Perfil</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {usuario ? `${usuario.nome} · ${usuario.matricula}` : "Carregando…"}
        </p>
      </Item>

      <SecaoAvatar />
      <Secao2FA />
      <SecaoSenha />
    </PageStagger>
  );
}
