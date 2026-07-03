"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

export type Backend = "ollama" | "groq" | "mock";

// Em modo hospedado (VPS sem Ollama), a demo usa IA de nuvem por padrão e
// esconde a opção "Local". Controlado por NEXT_PUBLIC_PRISMA_HOSTED em build.
const HOSTED = process.env.NEXT_PUBLIC_PRISMA_HOSTED === "1";

const TODOS: { id: Backend; label: string; hint: string }[] = [
  { id: "ollama", label: "Local", hint: "Ollama · privado/offline" },
  { id: "groq", label: "Nuvem", hint: "Groq · baixa latência" },
  { id: "mock", label: "Demo", hint: "determinístico" },
];

export const BACKENDS = HOSTED ? TODOS.filter((b) => b.id !== "ollama") : TODOS;

type Ctx = { backend: Backend; setBackend: (b: Backend) => void };
const BackendCtx = createContext<Ctx | null>(null);

export function BackendProvider({ children }: { children: ReactNode }) {
  const [backend, setBackend] = useState<Backend>(HOSTED ? "groq" : "ollama");
  return <BackendCtx.Provider value={{ backend, setBackend }}>{children}</BackendCtx.Provider>;
}

export function useBackend() {
  const ctx = useContext(BackendCtx);
  if (!ctx) throw new Error("useBackend deve ser usado dentro de <BackendProvider>");
  return ctx;
}
