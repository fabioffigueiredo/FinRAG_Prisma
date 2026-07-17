/** Lê o cookie prisma_csrf (não-httpOnly de propósito) pro double-submit. */
export function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)prisma_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}
