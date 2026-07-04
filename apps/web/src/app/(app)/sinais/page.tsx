"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { TriangleAlert, ShieldQuestion, CircleCheck, Info } from "lucide-react";
import { getSinais, type SinaisResp, type Sinal } from "@/lib/api";
import { useFund } from "@/components/app/fund-context";
import { pp } from "@/lib/fund";
import { PageStagger, Item } from "@/components/app/reveal";
import { easeOutQuint } from "@/lib/motion";
import { cn } from "@/lib/utils";

const NIVEL = {
  alerta: { label: "Alerta", cor: "var(--destructive)", Icon: TriangleAlert },
  atencao: { label: "Atenção", cor: "var(--chart-5)", Icon: ShieldQuestion },
  ok: { label: "Tranquilo", cor: "var(--success)", Icon: CircleCheck },
} as const;

/** Conta de 0 até `alvo` uma vez, respeitando reduced-motion. */
function useCountUp(alvo: number, ms = 700) {
  const reduce = useReducedMotion();
  const [v, setV] = useState(reduce ? alvo : 0);
  const raf = useRef<number>(0);
  useEffect(() => {
    if (reduce) {
      setV(alvo);
      return;
    }
    let start: number | null = null;
    const tick = (t: number) => {
      if (start === null) start = t;
      const p = Math.min((t - start) / ms, 1);
      const eased = 1 - Math.pow(1 - p, 4); // ease-out-quart
      setV(alvo * eased);
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [alvo, ms, reduce]);
  return v;
}

export default function SinaisPage() {
  const { codigo, fundo } = useFund();
  const [data, setData] = useState<SinaisResp | null>(null);

  useEffect(() => {
    setData(null);
    getSinais(codigo).then(setData);
  }, [codigo]);

  return (
    <PageStagger className="mx-auto max-w-5xl space-y-6">
      <Item>
        <h1 className="font-display text-2xl font-semibold text-foreground">Sinais</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Alertas de <strong>apoio à decisão</strong> por estratégia — probabilidade de contribuição
          negativa no próximo período, cruzando o sentimento do radar com o resultado corrente.
          {fundo.fundo.nome !== "Alfa Multimercado FIC FIM" && " (Notícias semeadas referem-se ao Alfa no POC.)"}
        </p>
      </Item>

      {/* aviso legal — sempre visível */}
      {data?.aviso && (
        <Item className="flex items-start gap-2.5 rounded-lg border border-[var(--chart-5)]/30 bg-[var(--chart-5)]/10 p-3">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-[var(--chart-5)]" strokeWidth={1.75} />
          <p className="text-[12px] leading-relaxed text-foreground/80">{data.aviso}</p>
        </Item>
      )}

      {!data ? (
        <Item className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="animate-pulse card-surface p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-muted/50" />
                  <div className="space-y-1.5">
                    <div className="h-4 w-32 rounded bg-muted/50" />
                    <div className="h-3 w-16 rounded bg-muted/40" />
                  </div>
                </div>
                <div className="h-7 w-12 rounded bg-muted/50" />
              </div>
              <div className="mt-3 h-2 rounded-full bg-muted/40" />
            </div>
          ))}
        </Item>
      ) : !data.ok ? (
        <Item className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          Sem sinais — suba a API e as notícias classificadas do radar.
        </Item>
      ) : (
        <ul className="space-y-3">
          {data.sinais.map((s, i) => (
            <SinalCard key={s.estrategia} s={s} i={i} />
          ))}
        </ul>
      )}

      {data?.modelo && (
        <Item>
          <p className="text-[11px] text-muted-foreground">
            Modelo: <span className="font-mono">{data.modelo}</span> · sinal por regras transparentes,
            não por LLM. Validação estatística (backtest) entra no piloto.
          </p>
        </Item>
      )}
    </PageStagger>
  );
}

function SinalCard({ s, i }: { s: Sinal; i: number }) {
  const n = NIVEL[s.nivel];
  const prob = useCountUp(s.prob_neg);
  return (
    <motion.li
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: easeOutQuint, delay: i * 0.08 }}
      className="card-surface p-5 transition-colors hover:border-border/80"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ backgroundColor: `color-mix(in oklab, ${n.cor} 15%, transparent)` }}
          >
            <n.Icon className="h-5 w-5" style={{ color: n.cor }} strokeWidth={1.75} />
          </span>
          <div>
            <p className="text-[15px] font-medium text-foreground">{s.estrategia}</p>
            <p className="text-[12px]" style={{ color: n.cor }}>{n.label}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="tabular font-display text-2xl font-semibold" style={{ color: n.cor }}>
            {Math.round(prob)}%
          </p>
          <p className="text-[11px] text-muted-foreground">prob. de contribuição negativa</p>
        </div>
      </div>

      {/* barra de probabilidade */}
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted/60">
        <motion.div
          className="h-full origin-left rounded-full"
          style={{ width: `${s.prob_neg}%`, backgroundColor: n.cor }}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.7, ease: easeOutQuint, delay: 0.1 + i * 0.08 }}
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
        <span>Sentimento líquido: <span className="tabular text-foreground">{s.sentimento_liquido.toFixed(2)}</span></span>
        <span>Contribuição atual: <span className={cn("tabular", s.contribuicao_pp < 0 ? "text-[var(--destructive)]" : "text-foreground")}>{pp(s.contribuicao_pp)}</span></span>
        <span>{s.noticias_no_periodo} notícia(s)</span>
        {s.evidencias.map((e) => (
          <span key={e} className="rounded bg-muted/50 px-1.5 py-0.5 font-mono text-[10px]">{e}</span>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground/80">{s.base_calculo}</p>
    </motion.li>
  );
}
