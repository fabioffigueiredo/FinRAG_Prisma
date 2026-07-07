"use client";

import { motion, type HTMLMotionProps } from "motion/react";
import { stagger, staggerItem } from "@/lib/motion";

/**
 * Container de entrada escalonada para uma página/seção.
 * Filhos marcados com <Item> surgem em cascata. Honra reduced-motion
 * via MotionConfig no shell.
 */
export function PageStagger({
  children,
  step = 0.07,
  className,
  ...rest
}: { step?: number } & HTMLMotionProps<"div">) {
  return (
    <motion.div
      variants={stagger(step)}
      initial="hidden"
      animate="show"
      className={className}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

/** Filho de PageStagger — sobe + surge. */
export function Item({ children, className, ...rest }: HTMLMotionProps<"div">) {
  return (
    <motion.div variants={staggerItem} className={className} {...rest}>
      {children}
    </motion.div>
  );
}
