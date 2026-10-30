export type Ciclo = {
  ciclo: number;
  teto: string;
  tai: string | null;
  acerto_assistido: string | null;
  transferencia: string | null;
  confianca: string | null;
  dss: string | null;
  iic: string | null;
  gap: string | null;
  vies: string | null;
  decisao: string;
  evidencia_incompleta: string | null;
  teto_seguinte: string;
};

export type Estado = {
  id: string;
  etapa: string;
  ciclo: number;
  teto: number;
  com_ia: boolean;
  onloading: boolean;
  justificativa_exigida: boolean;
  restantes: number;
  dicas_usadas: number[];
  item: { id: string; enunciado: string } | null;
  ciclos: Ciclo[];
};

export type Dica = { nivel: number; texto: string; origem: "ia" | "pre-escrita"; motivo: string | null };

export type Saude = { ia_disponivel: boolean; modelo: string };

async function pedir<T>(caminho: string, corpo?: unknown): Promise<T> {
  const resposta = await fetch(`/api${caminho}`, {
    method: corpo === undefined ? "GET" : "POST",
    headers: corpo === undefined ? undefined : { "Content-Type": "application/json" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  const dados = await resposta.json();
  if (!resposta.ok) {
    const detalhe = dados?.detail;
    throw new Error(typeof detalhe === "string" ? detalhe : "Pedido recusado pela API.");
  }
  return dados as T;
}

export const api = {
  saude: () => pedir<Saude>("/saude"),
  iniciar: (participante: string) => pedir<Estado>("/sessoes", { participante }),
  responder: (id: string, resposta: string, confianca: number, justificativa: string) =>
    pedir<{ resultado: string | null; ciclo_fechado: Ciclo | null; estado: Estado }>(`/sessoes/${id}/respostas`, {
      resposta,
      confianca,
      justificativa,
    }),
  dica: (id: string, nivel: number, explicacao: string) => pedir<Dica>(`/sessoes/${id}/dicas`, { nivel, explicacao }),
};
