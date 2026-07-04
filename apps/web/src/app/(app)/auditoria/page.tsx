"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { ScrollText, ShieldAlert, RefreshCw } from "lucide-react";
import { getAuditoria, type Consulta } from "@/lib/api";
import { PageStagger, Item } from "@/components/app/reveal";
import { Button } from "@/components/ui/button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { cn } from "@/lib/utils";

export default function AuditoriaPage() {
  const [consultas, setConsultas] = useState<Consulta[]>([]);
  const [carregou, setCarregou] = useState(false);
  const [loading, setLoading] = useState(false);

  async function carregar() {
    setLoading(true);
    const r = await getAuditoria();
    setConsultas(r.consultas);
    setCarregou(true);
    setLoading(false);
  }

  useEffect(() => {
    carregar();
  }, []);

  return (
    <PageStagger className="mx-auto max-w-6xl space-y-6">
      <Item className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-foreground">Auditoria</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Toda consulta ao núcleo cognitivo fica registrada: pergunta, motor, fontes citadas,
            bloqueios do guardrail e hash da resposta. Sem dados pessoais.
          </p>
        </div>
        <Button
          onClick={carregar}
          disabled={loading}
          variant="outline"
          size="sm"
          className="shrink-0 text-muted-foreground"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} strokeWidth={1.75} /> Atualizar
        </Button>
      </Item>

      {!carregou ? (
        <Item className="overflow-hidden card-surface">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-4 border-b border-border/50 px-4 py-3 last:border-0">
              <div className="h-3 w-32 animate-pulse rounded bg-muted/50" />
              <div className="h-3 w-20 animate-pulse rounded bg-muted/40" />
              <div className="h-3 flex-1 animate-pulse rounded bg-muted/40" />
              <div className="h-3 w-14 animate-pulse rounded bg-muted/40" />
            </div>
          ))}
        </Item>
      ) : consultas.length === 0 ? (
        <Item className="rounded-xl border border-dashed border-border p-10 text-center">
          <ScrollText className="mx-auto h-7 w-7 text-muted-foreground" strokeWidth={1.5} />
          <p className="mt-3 text-sm text-muted-foreground">
            Nenhuma consulta registrada ainda — use o copiloto ou gere uma narrativa.
          </p>
        </Item>
      ) : (
        <Item className="card-surface">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                {["Quando", "Fundo", "Consulta", "Motor"].map((h) => (
                  <TableHead key={h} className="px-4 py-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    {h}
                  </TableHead>
                ))}
                <TableHead className="px-4 py-3 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Latência
                </TableHead>
                <TableHead className="px-4 py-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Fontes
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {consultas.map((c, i) => (
                <TableRow
                  key={i}
                  className="animate-rise border-border/50 align-top hover:bg-muted/20"
                  style={{ "--i": Math.min(i, 8) } as CSSProperties}
                >
                  <TableCell className="tabular px-4 py-2.5 font-mono text-[12px] text-muted-foreground">
                    {c.timestamp.replace("T", " ")}
                  </TableCell>
                  <TableCell className="px-4 py-2.5 font-mono text-[12px] text-muted-foreground">{c.fundo}</TableCell>
                  <TableCell className="max-w-[28rem] whitespace-normal px-4 py-2.5 text-foreground">
                    {c.pergunta}
                    {c.escopo && (
                      <span className="ml-2 rounded border border-[var(--chart-5)]/40 bg-[var(--chart-5)]/10 px-1.5 py-0.5 text-[10px] text-[var(--chart-5)]">
                        fora de escopo
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="px-4 py-2.5 text-muted-foreground">{c.backend}</TableCell>
                  <TableCell className="tabular px-4 py-2.5 text-right text-muted-foreground">
                    {(c.latency_ms / 1000).toFixed(1)}s
                  </TableCell>
                  <TableCell className="px-4 py-2.5">
                    <div className="flex max-w-[22rem] flex-wrap gap-1">
                      {c.fontes.map((f, j) => (
                        <span key={j} className="rounded bg-muted/50 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                          {f}
                        </span>
                      ))}
                      {c.bloqueados.map((b, j) => (
                        <span
                          key={`b${j}`}
                          className="flex items-center gap-1 rounded bg-[var(--destructive)]/10 px-1.5 py-0.5 font-mono text-[10px] text-[var(--destructive)]"
                        >
                          <ShieldAlert className="h-3 w-3" strokeWidth={1.75} /> {b}
                        </span>
                      ))}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Item>
      )}
    </PageStagger>
  );
}
