"use client";

import { MotionConfig } from "motion/react";

/**
 * Faz todo o movimento do app honrar prefers-reduced-motion:
 * "user" desliga transform/layout e mantém apenas crossfades quando
 * o SO pede menos movimento.
 */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
