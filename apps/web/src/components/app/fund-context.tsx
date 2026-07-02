"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { FUNDS, FUND_PADRAO, type Fundo } from "@/lib/fund";

type Ctx = { codigo: string; fundo: Fundo; setCodigo: (c: string) => void };
const FundCtx = createContext<Ctx | null>(null);

export function FundProvider({ children }: { children: ReactNode }) {
  const [codigo, setCodigo] = useState(FUND_PADRAO);
  return (
    <FundCtx.Provider value={{ codigo, fundo: FUNDS[codigo], setCodigo }}>
      {children}
    </FundCtx.Provider>
  );
}

export function useFund() {
  const ctx = useContext(FundCtx);
  if (!ctx) throw new Error("useFund deve ser usado dentro de <FundProvider>");
  return ctx;
}
