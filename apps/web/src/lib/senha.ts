/** Mesma política de services/prisma-api/senha_policy.py — feedback
 * imediato aqui, o servidor é quem de fato valida. */
export const SENHA_MIN_LEN = 10;

export type RegraSenha = { label: string; ok: boolean };

export function checklistSenha(senha: string): RegraSenha[] {
  return [
    { label: `mínimo de ${SENHA_MIN_LEN} caracteres`, ok: senha.length >= SENHA_MIN_LEN },
    { label: "1 letra maiúscula", ok: /[A-Z]/.test(senha) },
    { label: "1 letra minúscula", ok: /[a-z]/.test(senha) },
    { label: "1 dígito", ok: /\d/.test(senha) },
    { label: "1 caractere especial", ok: /[^A-Za-z0-9]/.test(senha) },
  ];
}

export function senhaValida(senha: string): boolean {
  return checklistSenha(senha).every((r) => r.ok);
}
