"use client";

import { useEffect, useState } from "react";
import { ScrollText, ShieldAlert, RefreshCw } from "lucide-react";
import { getAuditoria, type Consulta } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function AuditoriaPage() {
  const [consultas, setConsultas] = useState<Consulta[]>([]);
  const [carregou, setCarregou] = useState(false);

  async function carregar() {
    const r = await getAuditoria();
    setConsultas(r.consultas);
    setCarregou(true);
  }

  useEffect(() => {
    carregar();
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-foreground">Auditoria</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Toda consulta ao núcleo cognitivo fica registrada: pergunta, motor, fontes citadas,
            bloqueios do guardrail e hash da resposta. Sem dados pessoais.
          </p>
        </div>
        <button
          onClick={carregar}
          className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.75} /> Atualizar
        </button>
      </div>

      {carregou && consultas.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-10 text-center">
          <ScrollText className="mx-auto h-7 w-7 text-muted-foreground" strokeWidth={1.5} />
          <p className="mt-3 text-sm text-muted-foreground">
            Nenhuma consulta registrada ainda — use o copiloto ou gere uma narrativa.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-3 text-left font-medium">Quando</th>
                <th className="px-4 py-3 text-left font-medium">Fundo</th>
                <th className="px-4 py-3 text-left font-medium">Consulta</th>
                <th className="px-4 py-3 text-left font-medium">Motor</th>
                <th className="px-4 py-3 text-right font-medium">Latência</th>
                <th className="px-4 py-3 text-left font-medium">Fontes</th>
              </tr>
            </thead>
            <tbody>
              {consultas.map((c, i) => (
                <tr key={i} className="border-b border-border/50 align-top last:border-0">
                  <td className="tabular whitespace-nowrap px-4 py-2.5 font-mono text-[12px] text-muted-foreground">
                    {c.timestamp.replace("T", " ")}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[12px] text-muted-foreground">{c.fundo}</td>
                  <td className="max-w-[28rem] px-4 py-2.5 text-foreground">
                    {c.pergunta}
                    {c.escopo && (
                      <span className="ml-2 rounded border border-[var(--chart-5)]/40 bg-[var(--chart-5)]/10 px-1.5 py-0.5 text-[10px] text-[var(--chart-5)]">
                        fora de escopo
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{c.backend}</td>
                  <td className="tabular px-4 py-2.5 text-right text-muted-foreground">
                    {(c.latency_ms / 1000).toFixed(1)}s
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex max-w-[22rem] flex-wrap gap-1">
                      {c.fontes.map((f, j) => (
                        <span key={j} className="rounded bg-muted/50 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                          {f}
                        </span>
                      ))}
                      {c.bloqueados.map((b, j) => (
                        <span
                          key={`b${j}`}
                          className={cn(
                            "flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px]",
                            "bg-[var(--destructive)]/10 text-[var(--destructive)]",
                          )}
                        >
                          <ShieldAlert className="h-3 w-3" strokeWidth={1.75} /> {b}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
