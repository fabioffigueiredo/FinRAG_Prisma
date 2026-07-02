"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

export type Backend = "ollama" | "groq" | "mock";

export const BACKENDS: { id: Backend; label: string; hint: string }[] = [
  { id: "ollama", label: "Local", hint: "Ollama · privado/offline" },
  { id: "groq", label: "Nuvem", hint: "Groq · baixa latência" },
  { id: "mock", label: "Demo", hint: "determinístico" },
];

type Ctx = { backend: Backend; setBackend: (b: Backend) => void };
const BackendCtx = createContext<Ctx | null>(null);

export function BackendProvider({ children }: { children: ReactNode }) {
  const [backend, setBackend] = useState<Backend>("ollama");
  return <BackendCtx.Provider value={{ backend, setBackend }}>{children}</BackendCtx.Provider>;
}

export function useBackend() {
  const ctx = useContext(BackendCtx);
  if (!ctx) throw new Error("useBackend deve ser usado dentro de <BackendProvider>");
  return ctx;
}
