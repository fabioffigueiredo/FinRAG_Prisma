import React from "react";
import {
  AbsoluteFill, Sequence, Audio, OffthreadVideo,
  staticFile, useCurrentFrame, interpolate,
} from "remotion";
import { loadFont as loadFraunces } from "@remotion/google-fonts/Fraunces";
import { loadFont as loadGeist } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import timingsGestor from "./timings.json";
import timingsLinkedIn from "./timings-linkedin.json";
import timingsTutorial from "./timings-tutorial.json";

const { fontFamily: DISPLAY } = loadFraunces();
const { fontFamily: SANS } = loadGeist();
const { fontFamily: MONO } = loadMono();

const INK = "#07090F";
const GOLD = "#F0B952";
const MINT = "#5EEAD4";
const CORAL = "#FB7185";
const PAPER = "#F3EEE3";
const DIM = "#9AA1B0";

/* fundo atmosférico */
const Bg = ({ glow = "12% -8%" }) => (
  <AbsoluteFill style={{ background: INK }}>
    <AbsoluteFill style={{
      background: `radial-gradient(900px 600px at ${glow}, rgba(240,185,82,.14), transparent 60%),
                   radial-gradient(800px 700px at 100% 110%, rgba(94,234,212,.07), transparent 55%)`,
    }} />
  </AbsoluteFill>
);

const Kicker = ({ children, color = GOLD, size = 22 }) => (
  <div style={{ fontFamily: MONO, fontSize: size, letterSpacing: 6,
    textTransform: "uppercase", color }}>{children}</div>
);

/* legenda inferior queimada */
const Caption = ({ children, vertical = false }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 14], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{
      position: "absolute",
      left: vertical ? 48 : 80, right: vertical ? 48 : 80,
      bottom: vertical ? 150 : 64,
      display: "flex", alignItems: "center", gap: 14, opacity: o,
    }}>
      <div style={{ width: 10, height: 10, borderRadius: 3, background: GOLD,
        boxShadow: `0 0 14px ${GOLD}`, flex: "0 0 auto" }} />
      <div style={{
        fontFamily: MONO, fontSize: vertical ? 30 : 26, lineHeight: 1.35, color: PAPER,
        background: "rgba(7,9,15,.68)", padding: "12px 18px", borderRadius: 10,
      }}>{children}</div>
    </div>
  );
};

/* moldura de navegador com vídeo real do app */
const ClipFrame = ({ src, kicker, caption, kickerColor = GOLD, vertical = false }) => {
  const f = useCurrentFrame();
  const s = interpolate(f, [0, 22], [0.97, 1], { extrapolateRight: "clamp" });
  const y = interpolate(f, [0, 22], [40, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Bg glow="15% 0%" />
      <div style={{ position: "absolute", top: vertical ? 120 : 64, left: vertical ? 48 : 80 }}>
        <Kicker color={kickerColor} size={vertical ? 24 : 22}>{kicker}</Kicker>
      </div>
      <div style={{
        transform: `translateY(${y}px) scale(${s})`,
        width: vertical ? 990 : 1340, borderRadius: 16, overflow: "hidden",
        border: "1px solid rgba(240,185,82,.25)",
        boxShadow: "0 50px 120px -40px rgba(0,0,0,.85)", background: "#0C0F18",
      }}>
        <div style={{ height: 38, display: "flex", alignItems: "center", gap: 8,
          padding: "0 16px", background: "#0E1320",
          borderBottom: "1px solid rgba(255,255,255,.06)" }}>
          {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => (
            <div key={c} style={{ width: 12, height: 12, borderRadius: "50%", background: c }} />
          ))}
          <div style={{ fontFamily: MONO, fontSize: 13, color: DIM, marginLeft: 12 }}>
            prisma · localhost:3100
          </div>
        </div>
        <OffthreadVideo src={src} muted style={{ width: "100%", display: "block" }} />
      </div>
      <Caption vertical={vertical}>{caption}</Caption>
    </AbsoluteFill>
  );
};

/* cena de título */
const TitleScene = ({ kicker, title, accent, caption, vertical = false }) => {
  const f = useCurrentFrame();
  const y = interpolate(f, [0, 24], [26, 0], { extrapolateRight: "clamp" });
  const o = interpolate(f, [0, 20], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center",
      padding: vertical ? 70 : 140 }}>
      <Bg glow="50% 0%" />
      <div style={{ textAlign: "center", transform: `translateY(${y}px)`, opacity: o,
        maxWidth: vertical ? 920 : 1400 }}>
        {kicker ? <div style={{ marginBottom: 22 }}><Kicker>{kicker}</Kicker></div> : null}
        <div style={{ fontFamily: DISPLAY, fontWeight: 300,
          fontSize: vertical ? 66 : 76, color: PAPER, lineHeight: 1.12 }}>
          {title}{" "}
          {accent ? <span style={{ fontStyle: "italic", color: GOLD }}>{accent}</span> : null}
        </div>
      </div>
      {caption ? <Caption vertical={vertical}>{caption}</Caption> : null}
    </AbsoluteFill>
  );
};

/* encaixe: plataforma de atribuição + Prisma */
const ComplementScene = ({ caption }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [6, 24], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const Card = ({ title, sub, desc, color }) => (
    <div style={{
      width: 460, padding: "36px 32px", borderRadius: 18,
      background: "rgba(255,255,255,.03)", border: `1px solid ${color}40`,
    }}>
      <div style={{ fontFamily: MONO, fontSize: 18, letterSpacing: 2, textTransform: "uppercase", color }}>{sub}</div>
      <div style={{ fontFamily: DISPLAY, fontWeight: 300, fontSize: 40, color: PAPER, marginTop: 10, lineHeight: 1.1 }}>{title}</div>
      <div style={{ fontFamily: MONO, fontSize: 20, color: DIM, marginTop: 16, lineHeight: 1.4 }}>{desc}</div>
    </div>
  );
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Bg glow="50% 0%" />
      <div style={{ position: "absolute", top: 64, left: 80, zIndex: 1 }}>
        <Kicker>Encaixe com o que já existe</Kicker>
      </div>
      <div style={{ position: "relative", zIndex: 1, textAlign: "center", opacity: o }}>
        <div style={{ display: "flex", gap: 28, alignItems: "center", justifyContent: "center" }}>
          <Card sub="Plataforma de atribuição" title="Os números calculados" desc="contribuição por estratégia e ativo — já entregue" color={DIM} />
          <div style={{ fontFamily: DISPLAY, fontSize: 64, color: GOLD }}>+</div>
          <Card sub="Prisma" title="A explicação auditável" desc="narrativa, Q&A com citações e trilha" color={GOLD} />
        </div>
        <div style={{ fontFamily: DISPLAY, fontWeight: 300, fontSize: 44, color: PAPER, marginTop: 40 }}>
          = fechamento <span style={{ fontStyle: "italic", color: GOLD }}>mais rápido e rastreável</span>
        </div>
      </div>
      <Caption>{caption}</Caption>
    </AbsoluteFill>
  );
};

/* valor (honesto) */
const ValueScene = ({ caption }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Bg glow="20% 0%" />
      <div style={{ position: "absolute", top: 64, left: 80, zIndex: 1 }}>
        <Kicker>Vantagem & retorno</Kicker>
      </div>
      <div style={{ position: "relative", zIndex: 1, textAlign: "center" }}>
        <div style={{ display: "flex", gap: 28, justifyContent: "center" }}>
          {[
            ["Horas → minutos", "redação vira revisão"],
            ["Padronizado", "mesmo tom em todos os fundos"],
            ["100% local", "nenhum dado sai da máquina"],
          ].map(([h, s], i) => {
            const op = interpolate(f, [6 + i * 8, 22 + i * 8], [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={h} style={{
                width: 380, padding: "34px 28px", borderRadius: 16, opacity: op,
                background: "rgba(255,255,255,.03)", border: "1px solid rgba(240,185,82,.28)",
              }}>
                <div style={{ fontFamily: DISPLAY, fontSize: 34, color: PAPER }}>{h}</div>
                <div style={{ fontFamily: MONO, fontSize: 20, color: DIM, marginTop: 12 }}>{s}</div>
              </div>
            );
          })}
        </div>
        <div style={{ fontFamily: MONO, fontSize: 22, color: MINT, marginTop: 36 }}>
          Explica o resultado calculado — não recomenda, não prevê.
        </div>
      </div>
      <Caption>{caption}</Caption>
    </AbsoluteFill>
  );
};

/* fecho: CTA de piloto */
const ClosingScene = ({ caption, vertical = false, cta, sub }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [6, 24], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Bg glow="50% 0%" />
      <div style={{ textAlign: "center", position: "relative", zIndex: 1, opacity: o,
        padding: vertical ? "0 60px" : 0 }}>
        {!vertical && (
          <div style={{ display: "flex", gap: 56, justifyContent: "center", marginBottom: 40 }}>
            {[["1 fundo", "piloto"], ["<15 min", "comentário revisado"], ["100%", "auditável"]].map(([n, l]) => (
              <div key={l}>
                <div style={{ fontFamily: DISPLAY, fontWeight: 300, fontSize: 64, color: GOLD }}>{n}</div>
                <div style={{ fontFamily: MONO, fontSize: 18, color: DIM,
                  textTransform: "uppercase", letterSpacing: 1 }}>{l}</div>
              </div>
            ))}
          </div>
        )}
        <div style={{ fontFamily: DISPLAY, fontWeight: 300,
          fontSize: vertical ? 62 : 76, color: PAPER, lineHeight: 1.1 }}>
          A atribuição de performance,<br />
          <span style={{ fontStyle: "italic", color: GOLD }}>explicada.</span>
        </div>
        <div style={{ fontFamily: MONO, fontSize: vertical ? 26 : 24, color: MINT, marginTop: 36 }}>
          {cta}
        </div>
        <div style={{ fontFamily: MONO, fontSize: vertical ? 20 : 22, color: DIM, marginTop: 18 }}>
          {sub}
        </div>
      </div>
      <Caption vertical={vertical}>{caption}</Caption>
    </AbsoluteFill>
  );
};

/* ===================== GESTOR · 1920×1080 ===================== */
const GESTOR_SCENES = [
  (b) => <TitleScene title="Prisma —" accent="a atribuição de performance, explicada." caption={b.text} />,
  (b) => <TitleScene kicker="O problema do fechamento" title="Os números ficam prontos." accent="O texto, não." caption={b.text} />,
  (b) => <ClipFrame src={staticFile("clips/cockpit.mp4")} kicker="Narrativa gerada · fontes citadas" caption={b.text} />,
  (b) => <ClipFrame src={staticFile("clips/radar.mp4")} kicker="Radar de Mercado · sentimento por estratégia" caption={b.text} kickerColor={MINT} />,
  (b) => <ClipFrame src={staticFile("clips/perguntas.mp4")} kicker="O gestor pergunta · o sistema responde" caption={b.text} />,
  (b) => <ClipFrame src={staticFile("clips/guardrail.mp4")} kicker="Guardrails · o que ele recusa" caption={b.text} kickerColor={CORAL} />,
  (b) => <ClipFrame src={staticFile("clips/auditoria.mp4")} kicker="Trilha de auditoria · compliance" caption={b.text} kickerColor={MINT} />,
  (b) => <ClipFrame src={staticFile("clips/sinais.mp4")} kicker="Sinais · apoio à decisão (não recomendação)" caption={b.text} kickerColor={CORAL} />,
  (b) => <ComplementScene caption={b.text} />,
  (b) => <ValueScene caption={b.text} />,
  (b) => <ClosingScene caption={b.text} cta="Vamos validar um piloto com um fundo real?" sub="Prisma · Attribution Intelligence" />,
];

export const PrismaGestorVideo = () => (
  <AbsoluteFill style={{ background: INK, fontFamily: SANS }}>
    <Audio src={staticFile("narration-gestor.mp3")} />
    {timingsGestor.beats.map((b) => {
      const render = GESTOR_SCENES[b.index];
      if (!render) return null;
      return (
        <Sequence key={b.index} from={b.startFrame} durationInFrames={b.durFrames + 18}>
          {render(b)}
        </Sequence>
      );
    })}
  </AbsoluteFill>
);

/* ===================== LINKEDIN · 1080×1920 ===================== */
const LINKEDIN_SCENES = [
  (b) => <TitleScene vertical title="A planilha fica pronta." accent="O texto, não." caption={b.text} />,
  (b) => <ClipFrame vertical src={staticFile("clips/cockpit.mp4")} kicker="Narrativa com fontes" caption={b.text} />,
  (b) => <ClipFrame vertical src={staticFile("clips/radar.mp4")} kicker="Radar de Mercado" caption={b.text} kickerColor={MINT} />,
  (b) => <ClipFrame vertical src={staticFile("clips/guardrail.mp4")} kicker="Guardrails · recusa na tela" caption={b.text} kickerColor={CORAL} />,
  (b) => <ClipFrame vertical src={staticFile("clips/auditoria.mp4")} kicker="Trilha de auditoria" caption={b.text} kickerColor={MINT} />,
  (b) => <TitleScene vertical kicker="Privacidade" title="Roda 100% local." accent="Nenhum dado sai da máquina." caption={b.text} />,
  (b) => <ClosingScene vertical caption={b.text} cta="Código aberto · demo reproduzível" sub="github.com/fabioffigueiredo/FinRAG_Prisma · link no 1º comentário" />,
];

export const PrismaLinkedInVideo = () => (
  <AbsoluteFill style={{ background: INK, fontFamily: SANS }}>
    <Audio src={staticFile("narration-linkedin.mp3")} />
    {timingsLinkedIn.beats.map((b) => {
      const render = LINKEDIN_SCENES[b.index];
      if (!render) return null;
      return (
        <Sequence key={b.index} from={b.startFrame} durationInFrames={b.durFrames + 18}>
          {render(b)}
        </Sequence>
      );
    })}
  </AbsoluteFill>
);

/* ===================== TUTORIAL · 1920×1080 (para o GitHub) ===================== */
const TUTORIAL_SCENES = [
  (b) => <TitleScene kicker="Tutorial" title="Como usar o Prisma," accent="tela por tela." caption={b.text} />,
  (b) => <TitleScene kicker="Passo 0 · Setup" title="Dois comandos e o app está no ar." accent="Instruções no README." caption={b.text} />,
  (b) => <ClipFrame src={staticFile("clips/cockpit.mp4")} kicker="Passo 1 · Cockpit" caption={b.text} />,
  (b) => <ClipFrame src={staticFile("clips/cockpit.mp4")} kicker="Passo 2 · Gerar narrativa ao vivo" caption={b.text} />,
  (b) => <ClipFrame src={staticFile("clips/atribuicao.mp4")} kicker="Passo 3 · Atribuição e drill" caption={b.text} />,
  (b) => <ClipFrame src={staticFile("clips/radar.mp4")} kicker="Passo 4 · Radar de Mercado" caption={b.text} kickerColor={MINT} />,
  (b) => <ClipFrame src={staticFile("clips/perguntas.mp4")} kicker="Passo 5 · Pergunte ao copiloto" caption={b.text} />,
  (b) => <ClipFrame src={staticFile("clips/guardrail.mp4")} kicker="Passo 6 · Guardrails em ação" caption={b.text} kickerColor={CORAL} />,
  (b) => <ClipFrame src={staticFile("clips/auditoria.mp4")} kicker="Passo 7 · Auditoria" caption={b.text} kickerColor={MINT} />,
  (b) => <ClipFrame src={staticFile("clips/sinais.mp4")} kicker="Passo 8 · Sinais (apoio à decisão)" caption={b.text} kickerColor={CORAL} />,
  (b) => <ClipFrame src={staticFile("clips/motor.mp4")} kicker="Passo 9 · IA local ou nuvem (API)" caption={b.text} />,
  (b) => <ClipFrame src={staticFile("clips/standalone.mp4")} kicker="Passo 10 · Modo standalone" caption={b.text} kickerColor={MINT} />,
  (b) => <ClosingScene caption={b.text} cta="git clone · README com o passo a passo" sub="github.com/fabioffigueiredo/FinRAG_Prisma" />,
];

export const PrismaTutorialVideo = () => (
  <AbsoluteFill style={{ background: INK, fontFamily: SANS }}>
    <Audio src={staticFile("narration-tutorial.mp3")} />
    {timingsTutorial.beats.map((b) => {
      const render = TUTORIAL_SCENES[b.index];
      if (!render) return null;
      return (
        <Sequence key={b.index} from={b.startFrame} durationInFrames={b.durFrames + 18}>
          {render(b)}
        </Sequence>
      );
    })}
  </AbsoluteFill>
);
