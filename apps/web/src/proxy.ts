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

  if (pathname === "/login" || pathname === "/cadastro") {
    if (temSessao) {
      const raiz = request.nextUrl.clone();
      raiz.pathname = "/";
      return NextResponse.redirect(raiz);
    }
    return NextResponse.next();
  }

  // /ativar-conta/{token} é pública em qualquer estado de sessão — o próprio
  // POST /auth/ativar-conta emite uma sessão nova ao final (mesmo contrato
  // de um link de "definir senha" aberto de qualquer lugar).
  if (pathname.startsWith("/ativar-conta/")) {
    return NextResponse.next();
  }

  if (!temSessao) {
    // request.nextUrl.clone() (não `new URL(path, request.url)`) — só o
    // clone preserva o basePath internamente; um `new URL("/login", ...)`
    // substitui o path inteiro a partir da origem e derruba o prefixo
    // `/prisma` do deploy hospedado (achado em produção: redirect ia pra
    // wiki.ioi.ia.br/login, sem o /prisma, 404).
    const destino = request.nextUrl.clone();
    destino.pathname = "/login";
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
