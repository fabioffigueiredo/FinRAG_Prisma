"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { UploadCloud, FileSpreadsheet, ArrowRight, Plug, Server, Check, Loader2 } from "lucide-react";
import { ingerir, type IngestResp } from "@/lib/api";
import { pct, pp } from "@/lib/fund";
import { Kpi, SectionTitle } from "@/components/app/kpi";
import { ContributionBars } from "@/components/charts/contribution-bars";
import { PageStagger, Item } from "@/components/app/reveal";
import { Button } from "@/components/ui/button";
import { easeOutQuint } from "@/lib/motion";

export default function StandalonePage() {
  const [drag, setDrag] = useState(false);
  const [res, setRes] = useState<IngestResp | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function processar(nome: string, texto: string) {
    setLoading(true);
    const r = await ingerir(nome, texto);
    setRes(r);
    setLoading(false);
  }

  async function onFile(file: File) {
    processar(file.name, await file.text());
  }

  async function usarExemplo() {
    const t = await fetch("/PA_ALFA-33_2T2026.csv").then((r) => r.text());
    processar("PA_ALFA-33_2T2026.csv", t);
  }

  // atalho de apresentação: /standalone?demo=1 carrega o exemplo automaticamente
  useEffect(() => {
    if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("demo") === "1") {
      usarExemplo();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <PageStagger className="mx-auto max-w-5xl space-y-6">
      <Item>
        <h1 className="font-display text-2xl font-semibold text-foreground">Modo standalone</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          O mesmo núcleo cognitivo, sem backend ao vivo: suba um export de atribuição (CSV) e o
          Prisma lê, resume e deixa consultável. É o produto companheiro.
        </p>
      </Item>

      <Item className="grid gap-4 sm:grid-cols-2">
        <div className="card-surface p-5">
          <Plug className="h-5 w-5 text-primary" strokeWidth={1.75} />
          <h2 className="mt-3 text-sm font-semibold text-foreground">Adaptador integrado</h2>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Consome o JSON da plataforma de atribuição via API e explica os números que já existem.
          </p>
        </div>
        <div className="rounded-xl border border-primary/25 bg-card p-5">
          <Server className="h-5 w-5 text-primary" strokeWidth={1.75} />
          <h2 className="mt-3 text-sm font-semibold text-foreground">Adaptador arquivo (este modo)</h2>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Ingere exports (CSV) e monta a leitura localmente — sem integração.
          </p>
        </div>
      </Item>

      <AnimatePresence mode="wait">
        {!res ? (
          <motion.div
            key="dropzone"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.99 }}
            transition={{ duration: 0.3, ease: easeOutQuint }}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              const f = e.dataTransfer.files?.[0];
              if (f) onFile(f);
            }}
            style={{
              borderColor: drag ? "var(--primary)" : "var(--border)",
              backgroundColor: drag ? "color-mix(in oklab, var(--primary) 5%, transparent)" : "transparent",
              scale: drag ? 1.01 : 1,
            }}
            className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 text-center transition-colors"
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
            />
            <motion.div animate={{ y: drag ? -4 : 0 }} transition={{ duration: 0.2 }}>
              {loading ? (
                <Loader2 className="h-8 w-8 animate-spin text-primary" strokeWidth={1.5} />
              ) : (
                <UploadCloud className="h-8 w-8 text-muted-foreground" strokeWidth={1.5} />
              )}
            </motion.div>
            <p className="mt-3 text-sm text-foreground">
              {loading ? "Lendo e resumindo…" : "Arraste um export de atribuição (CSV) aqui"}
            </p>
            <p className="mt-1 text-[12px] text-muted-foreground">
              colunas: <span className="font-mono">estrategia, contribuicao_pp, peso_medio</span>
            </p>
            <div className="mt-4 flex gap-2">
              <Button onClick={() => inputRef.current?.click()} variant="outline" size="lg">
                Selecionar arquivo
              </Button>
              <Button onClick={usarExemplo} size="lg">
                Usar arquivo de exemplo
              </Button>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="results"
            className="space-y-4"
            variants={{ hidden: {}, show: { transition: { staggerChildren: 0.07 } } }}
            initial="hidden"
            animate="show"
          >
            <Item className="flex items-center gap-2 rounded-lg border border-[var(--success)]/30 bg-[var(--success)]/10 px-3 py-2 text-sm text-[var(--success)]">
              <Check className="h-4 w-4" strokeWidth={2} />
              <FileSpreadsheet className="h-4 w-4" strokeWidth={1.75} />
              {res.fundo?.nome} · {res.n_estrategias} estratégias ingeridas
              {res.fallback && <span className="text-muted-foreground"> · leitura local</span>}
              <button onClick={() => setRes(null)} className="ml-auto text-xs text-muted-foreground transition-colors hover:text-foreground">
                trocar arquivo
              </button>
            </Item>

            {res.resumo && (
              <Item className="grid grid-cols-3 gap-4">
                <Kpi label="Retorno da cota" value={pct(res.resumo.retorno_cota)} accent />
                <Kpi label="Excesso vs CDI" value={pp(res.resumo.excesso_pp)} tone="positive" />
                <Kpi label="% do CDI" value={`${res.resumo.pct_cdi.toLocaleString("pt-BR")}%`} />
              </Item>
            )}

            <Item className="card-surface p-5">
              <SectionTitle hint="do arquivo importado">Contribuição por estratégia</SectionTitle>
              {res.estrategias && <ContributionBars estrategias={res.estrategias} />}
            </Item>

            <Item>
              <Link
                href="/copiloto"
                className="group inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
              >
                Perguntar ao Prisma sobre este fundo
                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" strokeWidth={2} />
              </Link>
            </Item>
          </motion.div>
        )}
      </AnimatePresence>
    </PageStagger>
  );
}
