"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { FileEdit, Eye, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { easeOutQuint } from "@/lib/motion";

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
    <div className="card-surface p-4">
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
                <motion.span
                  animate={{
                    borderColor: feito ? "color-mix(in oklab, var(--success) 40%, transparent)" : "var(--border)",
                    backgroundColor: feito ? "color-mix(in oklab, var(--success) 15%, transparent)" : "transparent",
                    color: feito ? "var(--success)" : "var(--muted-foreground)",
                    scale: i === idx ? [1, 1.12, 1] : 1,
                  }}
                  transition={{ duration: 0.35, ease: easeOutQuint }}
                  className="flex h-8 w-8 items-center justify-center rounded-full border"
                >
                  <Icon className="h-4 w-4" strokeWidth={1.75} />
                </motion.span>
                <span className={cn("text-[13px] transition-colors", feito ? "text-foreground" : "text-muted-foreground")}>
                  {p.label}
                </span>
              </div>
              {i < PASSOS.length - 1 && (
                <span className="mx-3 h-px flex-1 overflow-hidden bg-border">
                  <motion.span
                    className="block h-full origin-left bg-[var(--success)]/50"
                    initial={false}
                    animate={{ scaleX: i < idx ? 1 : 0 }}
                    transition={{ duration: 0.4, ease: easeOutQuint }}
                  />
                </span>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <AnimatePresence mode="wait">
          <motion.p
            key={estado}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
            className="text-[12px] text-muted-foreground"
          >
            {estado === "aprovado" && aprovador
              ? `Aprovado por ${aprovador.nome} · ${aprovador.hora}`
              : estado === "revisao"
                ? "Revise a síntese antes de aprovar."
                : "Envie para revisão quando a síntese estiver pronta."}
          </motion.p>
        </AnimatePresence>
        <div className="flex shrink-0 gap-2">
          {estado !== "aprovado" ? (
            <Button onClick={avancar} size="lg">
              {estado === "rascunho" ? "Enviar para revisão" : "Aprovar comentário"}
            </Button>
          ) : (
            <>
              <Button onClick={reabrir} variant="outline" size="lg" className="text-muted-foreground">
                Reabrir
              </Button>
              <Button
                size="lg"
                onClick={() => window.print()}
                className="bg-[var(--success)]/15 text-[var(--success)] hover:bg-[var(--success)]/25"
              >
                <Check className="h-3.5 w-3.5" strokeWidth={2} /> Exportar PDF
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
