/** Medida da API em porcentagem; indisponível nunca vira zero. */
export function porcento(valor: string | null): string {
  return valor === null ? "indisponível" : `${Math.round(Number(valor) * 100)}%`;
}
