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
  item: { id: string; enunciado: string; tamanho_max: number } | null;
  steam: Projeto | null;
  retencao: { concluida: boolean; disponivel: boolean; abre_em: string | null } | null;
};

export type Projeto = {
  titulo: string;
  enunciado: string;
  partes: { parte: string; pergunta: string; unidade: string | null; tamanho_max: number }[];
  justificativa: { pergunta: string; tamanho_max: number };
};

export type ResumoDaSubmissao = { id: number; cenario: string; criado_em: string; avaliadores: string[] };

export type Submissao = ResumoDaSubmissao & {
  pergunta: string | null;
  justificativa: string;
  rubrica: {
    titulo: string;
    descricao: string;
    criterios: { criterio: string; descricao: string; niveis: { nivel: string; pontos: number; descricao: string }[] }[];
  };
};

export type Dica = { nivel: number; texto: string; origem: "ia" | "pre-escrita"; motivo: string | null };

export type Saude = { ia_disponivel: boolean; modelo: string };

export class ErroDaApi extends Error {
  constructor(
    mensagem: string,
    readonly status: number,
  ) {
    super(mensagem);
  }
}

const SEM_CONEXAO = "Não foi possível falar com o sistema. Confira com o pesquisador e tente de novo.";

/** Mensagem legível de qualquer corpo de erro, inclusive a lista de validação do FastAPI. */
export function mensagemDoErro(corpo: unknown): string {
  const detalhe = (corpo as { detail?: unknown } | null)?.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe)) return "Algum campo está fora do formato esperado. Confira e tente de novo.";
  return "O sistema recusou o pedido. Tente de novo.";
}

async function pedir<T>(caminho: string, corpo?: unknown, chave?: string): Promise<T> {
  let resposta: Response;
  const cabecalhos: Record<string, string> = {};
  if (corpo !== undefined) cabecalhos["Content-Type"] = "application/json";
  if (chave !== undefined) cabecalhos["X-Chave-Professor"] = chave;
  try {
    resposta = await fetch(`/api${caminho}`, {
      method: corpo === undefined ? "GET" : "POST",
      headers: Object.keys(cabecalhos).length ? cabecalhos : undefined,
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch {
    throw new ErroDaApi(SEM_CONEXAO, 0);
  }
  let dados: unknown = null;
  try {
    dados = await resposta.json();
  } catch {
    // Proxy fora do ar devolve HTML ou corpo vazio: vale a mensagem de conexão.
  }
  if (!resposta.ok) {
    throw new ErroDaApi(dados === null ? SEM_CONEXAO : mensagemDoErro(dados), resposta.status);
  }
  return dados as T;
}

export const api = {
  saude: () => pedir<Saude>("/saude"),
  iniciar: (participante: string) => pedir<Estado>("/sessoes", { participante }),
  ler: (id: string) => pedir<Estado>(`/sessoes/${encodeURIComponent(id)}`),
  responder: (id: string, resposta: string, confianca: number, justificativa: string) =>
    pedir<{ ciclo_concluido: number | null; estado: Estado }>(`/sessoes/${encodeURIComponent(id)}/respostas`, {
      resposta,
      confianca,
      justificativa,
    }),
  iniciarRetencao: (id: string) => pedir<Estado>(`/sessoes/${encodeURIComponent(id)}/retencao`, {}),
  dica: (id: string, nivel: number, explicacao: string) =>
    pedir<Dica>(`/sessoes/${encodeURIComponent(id)}/dicas`, { nivel, explicacao }),
  steam: (id: string, partes: Record<string, string>, justificativa: string) =>
    pedir<Estado>(`/sessoes/${encodeURIComponent(id)}/steam`, { partes, justificativa }),
};

export const professor = {
  submissoes: (chave: string) => pedir<ResumoDaSubmissao[]>("/professor/submissoes", undefined, chave),
  submissao: (chave: string, id: number) => pedir<Submissao>(`/professor/submissoes/${id}`, undefined, chave),
  avaliar: (chave: string, id: number, avaliador: string, niveis: Record<string, string>) =>
    pedir<{ pontos: number; pontos_maximos: number }>(
      `/professor/submissoes/${id}/avaliacoes`,
      { avaliador, niveis },
      chave,
    ),
};
