"use client";

import { useEffect, useState, type CSSProperties, type FormEvent } from "react";
import { UserPlus, RefreshCw, Users, ShieldOff, ShieldX, UserCheck, UserX, Mail } from "lucide-react";
import { toast } from "sonner";
import {
  listarUsuarios,
  criarUsuario,
  atualizarUsuario,
  revogarSessao,
  resetar2FA,
  getHistoricoAcessos,
  listarPendentes,
  aprovarCadastro,
  rejeitarCadastro,
  criarConvite,
  type Usuario,
  type EventoAcesso,
  type PendenteCadastro,
} from "@/lib/api";
import { useSession } from "@/components/app/session-context";
import { PageStagger, Item } from "@/components/app/reveal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

type Papel = "analista" | "gestor" | "compliance";

/**
 * Copy institucional/de compliance — rascunho a partir do docstring do enum
 * `Papel` em db/models.py ("analista opera, gestor decide, compliance
 * audita"). Validar com o Fabio antes de considerar definitivo (é decisão de
 * produto/compliance, não de engenharia — ver Stage 8 do plano).
 */
const PAPEL_INFO: Record<Papel, { label: string; capacidade: string }> = {
  analista: {
    label: "Analista",
    capacidade:
      "Opera o dia a dia: consulta atribuição, gera narrativas, usa o copiloto. Não administra usuários nem decide o que é publicado.",
  },
  gestor: {
    label: "Gestor",
    capacidade:
      "Decide: além de operar, administra usuários da gestora e assina a narrativa publicada. Acesso completo à auditoria.",
  },
  compliance: {
    label: "Compliance",
    capacidade:
      "Audita: acesso à trilha de auditoria e à administração de usuários — foco em supervisão, não na operação diária.",
  },
};

const PAPEL_ITEMS = (Object.keys(PAPEL_INFO) as Papel[]).map((value) => ({
  value,
  label: PAPEL_INFO[value].label,
}));

/** Toast padrão pra qualquer ação que gera link de ativação (aprovação de
 * cadastro OU convite direto) — o link SEMPRE aparece aqui, mesmo quando o
 * e-mail foi enviado: rede de segurança se o e-mail cair no spam/falhar. */
function avisarLinkAtivacao(linkAtivacao: string, emailEnviado: boolean) {
  toast.success(emailEnviado ? "E-mail de ativação enviado." : "E-mail não pôde ser enviado — copie o link abaixo.", {
    description: linkAtivacao,
    action: {
      label: "Copiar link",
      onClick: () => {
        navigator.clipboard.writeText(linkAtivacao).then(
          () => toast.success("Link copiado."),
          () => toast.error("Não foi possível copiar — copie o link manualmente."),
        );
      },
    },
  });
}

function RoleBadge({ papel }: { papel: string }) {
  const info = PAPEL_INFO[papel as Papel];
  if (!info) return <Badge variant="outline">{papel}</Badge>;
  return (
    <Tooltip>
      <TooltipTrigger render={<Badge variant={papel === "gestor" ? "default" : "secondary"} className="cursor-default" />}>
        {info.label}
      </TooltipTrigger>
      <TooltipContent>{info.capacidade}</TooltipContent>
    </Tooltip>
  );
}

type ModoCriacao = "senha" | "convite";

type FormState = {
  matricula: string;
  nome: string;
  papel: Papel;
  senha: string;
  ativo: boolean;
  email: string;
  telefone: string;
  trocarSenha: boolean;
  modo: ModoCriacao;
};
const FORM_VAZIO: FormState = {
  matricula: "",
  nome: "",
  papel: "analista",
  senha: "",
  ativo: true,
  email: "",
  telefone: "",
  trocarSenha: false,
  modo: "senha",
};

function HistoricoAcessos({ usuarioId }: { usuarioId: number }) {
  const [eventos, setEventos] = useState<EventoAcesso[]>([]);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    let ativo = true;
    getHistoricoAcessos(usuarioId).then((r) => {
      if (ativo) {
        setEventos(r.eventos);
        setCarregando(false);
      }
    });
    return () => {
      ativo = false;
    };
  }, [usuarioId]);

  return (
    <div className="space-y-2 border-t border-border pt-4">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Histórico de acessos</p>
      {carregando ? (
        <p className="text-xs text-muted-foreground">Carregando…</p>
      ) : eventos.length === 0 ? (
        <p className="text-xs text-muted-foreground">Nenhum evento registrado.</p>
      ) : (
        <ul className="max-h-40 space-y-1 overflow-y-auto">
          {eventos.map((e, i) => (
            <li
              key={i}
              className="flex items-center justify-between gap-3 border-b border-border/50 py-1.5 text-xs last:border-0"
            >
              <span className="text-foreground">{e.pergunta}</span>
              <span className="tabular shrink-0 font-mono text-[11px] text-muted-foreground">
                {new Date(e.timestamp).toLocaleString("pt-BR")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PendentesSection({ onProcessado }: { onProcessado: () => void }) {
  const [pendentes, setPendentes] = useState<PendenteCadastro[]>([]);
  const [carregado, setCarregado] = useState(false);
  const [papeis, setPapeis] = useState<Record<number, Papel>>({});
  const [processando, setProcessando] = useState<number | null>(null);

  async function carregar() {
    const r = await listarPendentes();
    setPendentes(r.usuarios);
    setCarregado(true);
  }

  useEffect(() => {
    let ativo = true;
    listarPendentes().then((r) => {
      if (ativo) {
        setPendentes(r.usuarios);
        setCarregado(true);
      }
    });
    return () => {
      ativo = false;
    };
  }, []);

  async function onAprovar(p: PendenteCadastro) {
    setProcessando(p.id);
    const resultado = await aprovarCadastro(p.id, papeis[p.id] ?? "analista");
    setProcessando(null);
    if (!resultado.ok) {
      toast.error(resultado.erro);
      return;
    }
    avisarLinkAtivacao(resultado.linkAtivacao, resultado.emailEnviado);
    carregar();
    onProcessado();
  }

  async function onRejeitar(p: PendenteCadastro) {
    setProcessando(p.id);
    const resultado = await rejeitarCadastro(p.id);
    setProcessando(null);
    if (!resultado.ok) {
      toast.error(resultado.erro ?? "não foi possível rejeitar o cadastro");
      return;
    }
    toast.success("Cadastro rejeitado.");
    carregar();
  }

  if (!carregado || pendentes.length === 0) return null;

  return (
    <Item className="card-surface space-y-3 p-5">
      <div>
        <h2 className="text-sm font-semibold text-foreground">Cadastros pendentes</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">Autocadastro público aguardando sua aprovação.</p>
      </div>
      <ul className="space-y-2">
        {pendentes.map((p) => (
          <li
            key={p.id}
            className="flex flex-col gap-2 border-b border-border/50 pb-3 last:border-0 sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <p className="text-sm text-foreground">{p.nome}</p>
              <p className="tabular text-xs text-muted-foreground">
                {p.matricula}
                {p.email ? ` · ${p.email}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Select
                items={PAPEL_ITEMS}
                value={papeis[p.id] ?? "analista"}
                onValueChange={(v) => setPapeis((s) => ({ ...s, [p.id]: v as Papel }))}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {PAPEL_ITEMS.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
              <Button size="sm" variant="warning" disabled={processando === p.id} onClick={() => onAprovar(p)}>
                <UserCheck className="h-3.5 w-3.5" strokeWidth={1.75} /> Aprovar
              </Button>
              <Button size="sm" variant="destructive" disabled={processando === p.id} onClick={() => onRejeitar(p)}>
                <UserX className="h-3.5 w-3.5" strokeWidth={1.75} /> Rejeitar
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </Item>
  );
}

function UsuarioDialog({
  aberto,
  onOpenChange,
  editando,
  onSalvo,
}: {
  aberto: boolean;
  onOpenChange: (v: boolean) => void;
  editando: Usuario | null;
  onSalvo: () => void;
}) {
  const { usuario: sessao } = useSession();
  const [form, setForm] = useState<FormState>(FORM_VAZIO);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [revogando, setRevogando] = useState(false);
  const [resetando2FA, setResetando2FA] = useState(false);

  useEffect(() => {
    if (!aberto) return;
    setErro(null);
    setForm(
      editando
        ? {
            matricula: editando.matricula,
            nome: editando.nome,
            papel: editando.papel,
            senha: "",
            ativo: editando.ativo,
            email: editando.email ?? "",
            telefone: editando.telefone ?? "",
            trocarSenha: editando.trocar_senha_no_proximo_login,
            modo: "senha",
          }
        : FORM_VAZIO,
    );
  }, [aberto, editando]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);

    if (editando) {
      const resultado = await atualizarUsuario(editando.id, {
        nome: form.nome,
        papel: form.papel,
        ativo: form.ativo,
        email: form.email || undefined,
        telefone: form.telefone || undefined,
        trocar_senha_no_proximo_login: form.trocarSenha,
        ...(form.senha ? { senha: form.senha } : {}),
      });
      setEnviando(false);
      if (!resultado.ok) {
        setErro(resultado.erro);
        return;
      }
      toast.success("Usuário atualizado.");
      onOpenChange(false);
      onSalvo();
      return;
    }

    if (form.modo === "convite") {
      const resultado = await criarConvite({
        matricula: form.matricula,
        nome: form.nome,
        papel: form.papel,
        email: form.email,
        telefone: form.telefone || undefined,
      });
      setEnviando(false);
      if (!resultado.ok) {
        setErro(resultado.erro);
        return;
      }
      avisarLinkAtivacao(resultado.linkAtivacao, resultado.emailEnviado);
      onOpenChange(false);
      onSalvo();
      return;
    }

    const resultado = await criarUsuario({
      matricula: form.matricula,
      nome: form.nome,
      papel: form.papel,
      senha: form.senha,
      email: form.email || undefined,
      telefone: form.telefone || undefined,
      trocar_senha_no_proximo_login: form.trocarSenha,
    });
    setEnviando(false);
    if (!resultado.ok) {
      setErro(resultado.erro);
      return;
    }
    toast.success("Usuário criado.");
    onOpenChange(false);
    onSalvo();
  }

  async function onRevogar() {
    if (!editando) return;
    setRevogando(true);
    const resultado = await revogarSessao(editando.id);
    setRevogando(false);
    if (!resultado.ok) {
      toast.error(resultado.erro ?? "não foi possível revogar a sessão");
      return;
    }
    toast.success("Sessão revogada — o próximo acesso exige login novamente.");
  }

  async function onResetar2FA() {
    if (!editando) return;
    setResetando2FA(true);
    const resultado = await resetar2FA(editando.id);
    setResetando2FA(false);
    if (!resultado.ok) {
      toast.error(resultado.erro ?? "não foi possível resetar o 2FA");
      return;
    }
    toast.success("2FA resetado — o usuário vai configurar de novo no próximo login.");
    onSalvo();
  }

  return (
    <Dialog open={aberto} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{editando ? "Editar usuário" : "Novo usuário"}</DialogTitle>
          <DialogDescription>
            {editando ? `Atualizando ${editando.matricula}.` : "Cria um usuário na sua gestora."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit}>
          <FieldGroup>
            {erro && <p className="text-sm text-destructive">{erro}</p>}
            {!editando && (
              <Tabs value={form.modo} onValueChange={(v) => setForm((f) => ({ ...f, modo: v as ModoCriacao }))}>
                <TabsList className="w-full">
                  <TabsTrigger value="senha" className="flex-1">
                    Definir senha agora
                  </TabsTrigger>
                  <TabsTrigger value="convite" className="flex-1">
                    Enviar link de cadastro
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            )}
            {!editando && form.modo === "convite" && (
              <p className="text-xs text-muted-foreground">
                <Mail className="mr-1 inline h-3 w-3" strokeWidth={1.75} />
                O usuário recebe um link de uso único pra definir a própria senha e configurar o 2FA.
              </p>
            )}
            <Field>
              <FieldLabel htmlFor="matricula">Matrícula</FieldLabel>
              <Input
                id="matricula"
                value={form.matricula}
                disabled={!!editando}
                onChange={(e) => setForm((f) => ({ ...f, matricula: e.target.value }))}
                required
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="nome">Nome</FieldLabel>
              <Input id="nome" value={form.nome} onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))} required />
            </Field>
            <Field>
              <FieldLabel htmlFor="email">E-mail{!editando && form.modo === "convite" ? "" : " (opcional)"}</FieldLabel>
              <Input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                required={!editando && form.modo === "convite"}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="telefone">Telefone</FieldLabel>
              <Input
                id="telefone"
                value={form.telefone}
                onChange={(e) => setForm((f) => ({ ...f, telefone: e.target.value }))}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="papel">Papel</FieldLabel>
              <Select items={PAPEL_ITEMS} value={form.papel} onValueChange={(v) => setForm((f) => ({ ...f, papel: v as Papel }))}>
                <SelectTrigger id="papel" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {PAPEL_ITEMS.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            {(editando || form.modo === "senha") && (
              <Field>
                <FieldLabel htmlFor="senha">{editando ? "Nova senha (opcional)" : "Senha"}</FieldLabel>
                <PasswordInput
                  id="senha"
                  value={form.senha}
                  onChange={(e) => setForm((f) => ({ ...f, senha: e.target.value }))}
                  required={!editando}
                />
              </Field>
            )}
            {editando && (
              <Field orientation="horizontal">
                <Checkbox
                  id="ativo"
                  checked={form.ativo}
                  onCheckedChange={(v) => setForm((f) => ({ ...f, ativo: v === true }))}
                />
                <FieldLabel htmlFor="ativo" className="font-normal">
                  Ativo
                </FieldLabel>
              </Field>
            )}
            {(editando || form.modo === "senha") && (
              <Field orientation="horizontal">
                <Checkbox
                  id="trocar-senha"
                  checked={form.trocarSenha}
                  onCheckedChange={(v) => setForm((f) => ({ ...f, trocarSenha: v === true }))}
                />
                <FieldLabel htmlFor="trocar-senha" className="font-normal">
                  Forçar troca de senha no próximo login
                </FieldLabel>
              </Field>
            )}

            {editando && (
              <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
                <p className="text-xs text-muted-foreground">
                  Derruba a sessão ativa — o próximo acesso exige login de novo.
                </p>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  disabled={revogando || sessao?.matricula === editando.matricula}
                  onClick={onRevogar}
                >
                  <ShieldOff className="h-3.5 w-3.5" strokeWidth={1.75} />
                  {revogando ? "Revogando…" : "Revogar sessão ativa"}
                </Button>
              </div>
            )}
            {editando && editando.totp_ativado && (
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground">
                  Pra perda do celular/app autenticador — sem isso, o usuário fica travado na 2ª etapa do login pra sempre.
                </p>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  disabled={resetando2FA || sessao?.matricula === editando.matricula}
                  onClick={onResetar2FA}
                >
                  <ShieldX className="h-3.5 w-3.5" strokeWidth={1.75} />
                  {resetando2FA ? "Resetando…" : "Resetar 2FA"}
                </Button>
              </div>
            )}
            {editando && <HistoricoAcessos usuarioId={editando.id} />}

            <DialogFooter>
              <Button type="submit" variant="warning" disabled={enviando}>
                {enviando
                  ? "Salvando…"
                  : !editando && form.modo === "convite"
                    ? "Enviar convite"
                    : "Salvar"}
              </Button>
            </DialogFooter>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function UsuariosPage() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [carregou, setCarregou] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dialogAberto, setDialogAberto] = useState(false);
  const [editando, setEditando] = useState<Usuario | null>(null);

  async function carregar() {
    setLoading(true);
    const r = await listarUsuarios();
    setUsuarios(r.usuarios);
    setCarregou(true);
    setLoading(false);
  }

  useEffect(() => {
    carregar();
  }, []);

  function abrirNovo() {
    setEditando(null);
    setDialogAberto(true);
  }

  function abrirEdicao(u: Usuario) {
    setEditando(u);
    setDialogAberto(true);
  }

  return (
    <PageStagger className="mx-auto max-w-5xl space-y-6">
      <Item className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-foreground">Usuários</h1>
          <p className="mt-1 text-sm text-muted-foreground">Quem acessa o Prisma na sua gestora, e com qual papel.</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button onClick={carregar} disabled={loading} variant="outline" size="sm" className="text-muted-foreground">
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} strokeWidth={1.75} /> Atualizar
          </Button>
          <Button onClick={abrirNovo} variant="warning" size="sm">
            <UserPlus className="h-3.5 w-3.5" strokeWidth={1.75} /> Novo usuário
          </Button>
        </div>
      </Item>

      <PendentesSection onProcessado={carregar} />

      {!carregou ? (
        <Item className="overflow-hidden card-surface">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-4 border-b border-border/50 px-4 py-3 last:border-0">
              <div className="h-3 w-32 animate-pulse rounded bg-muted/50" />
              <div className="h-3 w-20 animate-pulse rounded bg-muted/40" />
              <div className="h-3 w-16 animate-pulse rounded bg-muted/40" />
              <div className="h-3 flex-1 animate-pulse rounded bg-muted/40" />
            </div>
          ))}
        </Item>
      ) : usuarios.length === 0 ? (
        <Item className="rounded-xl border border-dashed border-border p-10 text-center">
          <Users className="mx-auto h-7 w-7 text-muted-foreground" strokeWidth={1.5} />
          <p className="mt-3 text-sm text-muted-foreground">Nenhum usuário cadastrado ainda.</p>
        </Item>
      ) : (
        <Item className="card-surface">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                {["Nome", "Matrícula", "Papel", "Gestora", "Status"].map((h) => (
                  <TableHead key={h} className="px-4 py-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    {h}
                  </TableHead>
                ))}
                <TableHead className="px-4 py-3" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {usuarios.map((u, i) => (
                <TableRow
                  key={u.id}
                  className="animate-rise border-border/50 hover:bg-muted/20"
                  style={{ "--i": Math.min(i, 8) } as CSSProperties}
                >
                  <TableCell className="px-4 py-2.5 text-foreground">{u.nome}</TableCell>
                  <TableCell className="tabular px-4 py-2.5 font-mono text-[12px] text-muted-foreground">
                    {u.matricula}
                  </TableCell>
                  <TableCell className="px-4 py-2.5">
                    <RoleBadge papel={u.papel} />
                  </TableCell>
                  <TableCell className="px-4 py-2.5 text-muted-foreground">{u.gestora_nome}</TableCell>
                  <TableCell className="px-4 py-2.5">
                    {u.ativo ? <Badge variant="secondary">Ativo</Badge> : <Badge variant="outline">Inativo</Badge>}
                  </TableCell>
                  <TableCell className="px-4 py-2.5 text-right">
                    <Button variant="ghost" size="sm" onClick={() => abrirEdicao(u)}>
                      Editar
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Item>
      )}

      <UsuarioDialog aberto={dialogAberto} onOpenChange={setDialogAberto} editando={editando} onSalvo={carregar} />
    </PageStagger>
  );
}
