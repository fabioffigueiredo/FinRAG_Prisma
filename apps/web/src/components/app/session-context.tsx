"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getMe, logout as apiLogout, type MeResp } from "@/lib/api";

type Sessao = {
  usuario: MeResp | null;
  loading: boolean;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const SessionCtx = createContext<Sessao | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<MeResp | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ativo = true;
    getMe().then((u) => {
      if (ativo) {
        setUsuario(u);
        setLoading(false);
      }
    });
    return () => {
      ativo = false;
    };
  }, []);

  async function logout() {
    await apiLogout();
    setUsuario(null);
    window.location.href = "/login";
  }

  /** Reconsulta /auth/me — usado depois de trocar avatar/ativar 2FA pra
   * refletir na hora sem esperar um reload de página inteira. */
  async function refresh() {
    const u = await getMe();
    setUsuario(u);
  }

  return <SessionCtx.Provider value={{ usuario, loading, logout, refresh }}>{children}</SessionCtx.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionCtx);
  if (!ctx) throw new Error("useSession deve ser usado dentro de <SessionProvider>");
  return ctx;
}
