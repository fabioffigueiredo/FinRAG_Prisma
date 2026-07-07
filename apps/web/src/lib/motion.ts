import type { Transition, Variants } from "motion/react";

/**
 * Vocabulário de movimento do Prisma ("Obsidian Terminal").
 * Regra 100/300/500 · desaceleração exponencial · nunca bounce/elastic.
 * Todo consumidor roda sob <MotionConfig reducedMotion="user">, então
 * o próprio motion neutraliza transform/opacity quando o usuário pede
 * menos movimento — aqui só definimos a intenção.
 */

// cubic-bezier em array (formato do motion)
export const easeOutQuint = [0.22, 1, 0.36, 1] as const;
export const easeOutExpo = [0.16, 1, 0.3, 1] as const;
export const easeOutQuart = [0.25, 1, 0.5, 1] as const;

/** Entrada padrão de bloco: sobe + surge. */
export const rise: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: easeOutQuint } },
};

/** Container que escalona a entrada dos filhos (stagger). */
export function stagger(step = 0.06, delayChildren = 0): Variants {
  return {
    hidden: {},
    show: {
      transition: { staggerChildren: step, delayChildren },
    },
  };
}

/** Filho de uma lista/grid com stagger. */
export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: easeOutQuint } },
};

/** Bolha de mensagem do chat (entrada suave, viés lateral por papel). */
export function bubbleIn(from: "left" | "right" = "left"): Variants {
  return {
    hidden: { opacity: 0, y: 8, x: from === "right" ? 8 : -8 },
    show: {
      opacity: 1,
      y: 0,
      x: 0,
      transition: { duration: 0.4, ease: easeOutQuint },
    },
  };
}

/** Transição de estado curta e padrão (feedback/hover). */
export const snappy: Transition = { duration: 0.2, ease: easeOutQuart };

/** Popover/dropdown: abre com origem no topo. */
export const popover: Variants = {
  hidden: { opacity: 0, y: -6, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.18, ease: easeOutQuart } },
  exit: { opacity: 0, y: -6, scale: 0.98, transition: { duration: 0.12, ease: easeOutQuart } },
};
