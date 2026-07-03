"use client";

import { useState } from "react";
import { FileEdit, Eye, Check } from "lucide-react";
import { cn } from "@/lib/utils";

type Estado = "rascunho" | "revisao" | "aprovado";

const PASSOS: { id: Estado; label: string; icon: typeof FileEdit }[] = [
  { id: "rascunho", label: "Rascunho", icon: FileEdit },
  { id: "revisao", label: "Em revisão", icon: Eye },
  { id: "aprovado", label: "Aprovado", icon: Check },
];

/**
 * Aprovação humana obrigatória (human-in-the-loop): nenhum comentário é exportado
 * sem passar por revisão e aprovação. Requisito de governança (docs/GOVERNANCA_IA.md).
 */
export function ApprovalFlow() {
  const [estado, setEstado] = useState<Estado>("rascunho");
  const [aprovador, setAprovador] = useState<{ nome: string; hora: string } | null>(null);

  const idx = PASSOS.findIndex((p) => p.id === estado);

  function avancar() {
    if (estado === "rascunho") setEstado("revisao");
    else if (estado === "revisao") {
      setEstado("aprovado");
      setAprovador({
        nome: "Fabio F. Figueiredo",
        hora: new Date().toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }),
      });
    }
  }
  function reabrir() {
    setEstado("rascunho");
    setAprovador(null);
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-4 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          Fluxo de aprovação
        </span>
        <span className="text-[11px] text-muted-foreground">human-in-the-loop</span>
      </div>

      {/* trilha de passos */}
      <div className="flex items-center">
        {PASSOS.map((p, i) => {
          const feito = i <= idx;
          const Icon = p.icon;
          return (
            <div key={p.id} className="flex flex-1 items-center last:flex-none">
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full border transition-colors",
                    feito
                      ? "border-[var(--success)]/40 bg-[var(--success)]/15 text-[var(--success)]"
                      : "border-border text-muted-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" strokeWidth={1.75} />
                </span>
                <span className={cn("text-[13px]", feito ? "text-foreground" : "text-muted-foreground")}>
                  {p.label}
                </span>
              </div>
              {i < PASSOS.length - 1 && (
                <span className={cn("mx-3 h-px flex-1", i < idx ? "bg-[var(--success)]/40" : "bg-border")} />
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <p className="text-[12px] text-muted-foreground">
          {estado === "aprovado" && aprovador
            ? `Aprovado por ${aprovador.nome} · ${aprovador.hora}`
            : estado === "revisao"
              ? "Revise a síntese antes de aprovar."
              : "Envie para revisão quando a síntese estiver pronta."}
        </p>
        <div className="flex gap-2">
          {estado !== "aprovado" ? (
            <button
              onClick={avancar}
              className="rounded-lg bg-primary px-3.5 py-1.5 text-sm font-medium text-primary-foreground"
            >
              {estado === "rascunho" ? "Enviar para revisão" : "Aprovar comentário"}
            </button>
          ) : (
            <>
              <button
                onClick={reabrir}
                className="rounded-lg border border-border px-3.5 py-1.5 text-sm text-muted-foreground hover:text-foreground"
              >
                Reabrir
              </button>
              <button className="flex items-center gap-1.5 rounded-lg bg-[var(--success)]/15 px-3.5 py-1.5 text-sm font-medium text-[var(--success)]">
                <Check className="h-3.5 w-3.5" strokeWidth={2} /> Exportar PDF
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
