"use client";

import { useEffect, useRef, useState } from "react";
import { getFeed, type FeedResp } from "@/lib/api";

const INTERVALO_MS = 60_000;

/** Manchetes ao vivo com polling condicional (ETag): a cada minuto pergunta
 * se há lote novo; sem novidade a API devolve 304 e nada re-renderiza.
 * Pausa enquanto a aba está oculta para não gastar requisição à toa. */
export function useFeedRadar(): FeedResp | null {
  const [feed, setFeed] = useState<FeedResp | null>(null);
  const etag = useRef<string | null>(null);

  useEffect(() => {
    let vivo = true;

    async function atualizar() {
      if (document.visibilityState === "hidden") return;
      const r = await getFeed(etag.current);
      if (!vivo || !r.feed) return; // 304: nada mudou
      const novo = r.feed;
      if (novo.erro) {
        // Falha pontual (rede, 5xx) não apaga as manchetes já na tela:
        // mantém a lista e só sinaliza que ela pode estar desatualizada.
        // Mantém o ETag anterior para o próximo poll continuar barato.
        setFeed((anterior) => (anterior?.ok ? { ...anterior, desatualizado: novo.erro } : novo));
        return;
      }
      etag.current = r.etag;
      setFeed(novo);
    }

    void atualizar();
    const id = window.setInterval(atualizar, INTERVALO_MS);
    const aoVoltar = () => {
      if (document.visibilityState === "visible") void atualizar();
    };
    document.addEventListener("visibilitychange", aoVoltar);
    return () => {
      vivo = false;
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", aoVoltar);
    };
  }, []);

  return feed;
}

/** "há 12 min", "há 3 h" — o gestor lê frescor mais rápido que um timestamp. */
export function haQuanto(iso: string, agora: number = Date.now()): string {
  const min = Math.max(0, Math.round((agora - new Date(iso).getTime()) / 60_000));
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  return `há ${Math.round(min / 60)} h`;
}
