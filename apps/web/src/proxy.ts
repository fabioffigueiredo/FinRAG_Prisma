import { NextRequest, NextResponse } from "next/server";

const COOKIE_SESSAO = "prisma_session";

/**
 * Camada de UX, não de segurança — a autorização real é o backend
 * (`Depends(auth.get_usuario_atual)`/`exigir_papel` em cada rota FastAPI).
 * Só checa presença do cookie (não decodifica o JWT, nem precisa do
 * PRISMA_JWT_SECRET aqui — mantém o secret fora do runtime Edge/Node).
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const temSessao = request.cookies.has(COOKIE_SESSAO);

  if (pathname === "/login") {
    if (temSessao) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  if (!temSessao) {
    const destino = new URL("/login", request.url);
    destino.searchParams.set("from", pathname);
    return NextResponse.redirect(destino);
  }

  return NextResponse.next();
}

export const config = {
  // "/" precisa vir explícito: com basePath configurado (deploy hospedado,
  // ver next.config.ts), o regex compilado do padrão catch-all abaixo exige
  // uma barra depois do basePath pra casar — a raiz exata (`/prisma`, sem
  // barra final, que é pra onde o Next.js sempre normaliza `/prisma/`) fica
  // de fora e o middleware nunca roda nela. Achado em produção: raiz não
  // autenticada devolvia 200 direto, sem redirecionar pro /login.
  matcher: ["/", "/((?!_next/static|_next/image|favicon\\.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|mp4|mp3|ico)$).*)"],
};
