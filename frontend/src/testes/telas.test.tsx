import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Estado } from "../api/cliente";
import { App } from "../App";
import { Fim } from "../paginas/Fim";
import { Item } from "../paginas/Item";
import { Professor } from "../paginas/Professor";
import { Steam } from "../paginas/Steam";

function estado(mudancas: Partial<Estado> = {}): Estado {
  return {
    id: "s1",
    etapa: "pratica_assistida",
    ciclo: 1,
    teto: 2,
    com_ia: true,
    onloading: false,
    justificativa_exigida: false,
    restantes: 4,
    dicas_usadas: [],
    item: { id: "alg-eq-101", enunciado: "Resolva 2x + 3 = 11.", tamanho_max: 120 },
    steam: null,
    retencao: null,
    ...mudancas,
  };
}

function respostaJson(corpo: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("tela do problema", () => {
  it("sem IA não oferece dica nenhuma", () => {
    render(<Item estado={estado({ etapa: "desafio_independente", com_ia: false })} cicloConcluido={null} aoAvancar={() => {}} />);
    expect(screen.getByText("Sem dicas nesta parte: resolva sozinho.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Pergunta para pensar/ })).toBeNull();
  });

  it("bloqueia as dicas acima do teto e diz até onde vai", () => {
    render(<Item estado={estado({ teto: 2 })} cicloConcluido={null} aoAvancar={() => {}} />);
    expect(screen.getByText("Nesta rodada você pode usar as dicas até o nível 2.")).toBeTruthy();
    expect((screen.getByRole("button", { name: /2 · Ideia-chave/ }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole("button", { name: /3 · Primeiro passo/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("não envia sem a confiança escolhida, que começa vazia", async () => {
    const usuario = userEvent.setup();
    render(<Item estado={estado()} cicloConcluido={null} aoAvancar={() => {}} />);
    const enviar = screen.getByRole("button", { name: "Enviar resposta" }) as HTMLButtonElement;
    await usuario.type(screen.getByLabelText("Sua resposta"), "4");
    expect(enviar.disabled).toBe(true);
    await usuario.click(screen.getByLabelText("7"));
    expect(enviar.disabled).toBe(false);
  });

  it("em onloading pede a explicação antes da primeira dica", async () => {
    const usuario = userEvent.setup();
    render(<Item estado={estado({ onloading: true })} cicloConcluido={null} aoAvancar={() => {}} />);
    const dica = screen.getByRole("button", { name: /1 · Pergunta para pensar/ }) as HTMLButtonElement;
    expect(dica.disabled).toBe(true);
    await usuario.type(screen.getByLabelText(/conte o que você já tentou/), "tirei 3 dos dois lados");
    expect(dica.disabled).toBe(false);
  });

  it("com justificativa exigida, só envia depois de ela ser escrita, e manda tudo para a API", async () => {
    const usuario = userEvent.setup();
    const fetch = vi.fn((_url: string, _init?: RequestInit) =>
      respostaJson({ ciclo_concluido: null, estado: estado({ restantes: 3 }) }),
    );
    vi.stubGlobal("fetch", fetch);
    const aoAvancar = vi.fn();
    render(<Item estado={estado({ justificativa_exigida: true })} cicloConcluido={null} aoAvancar={aoAvancar} />);
    await usuario.type(screen.getByLabelText("Sua resposta"), "4");
    await usuario.click(screen.getByLabelText("9"));
    const enviar = screen.getByRole("button", { name: "Enviar resposta" }) as HTMLButtonElement;
    expect(enviar.disabled).toBe(true);
    await usuario.type(screen.getByLabelText(/como você chegou/), "subtraí e dividi");
    await usuario.click(enviar);
    expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({
      resposta: "4",
      confianca: 9,
      justificativa: "subtraí e dividi",
    });
    expect(aoAvancar).toHaveBeenCalledOnce();
  });

  it("não mostra acerto, desempenho nem condição ao fechar a rodada", () => {
    render(<Item estado={estado({ ciclo: 2 })} cicloConcluido={1} aoAvancar={() => {}} />);
    expect(screen.getByRole("status").textContent).toBe("Você terminou a rodada 1 de 3. Vamos para a próxima.");
    expect(document.body.textContent).not.toMatch(/%|acert|condição|fading|teto/i);
  });

  it("erro de rede vira mensagem em português com o próximo passo", async () => {
    const usuario = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    render(<Item estado={estado()} cicloConcluido={null} aoAvancar={() => {}} />);
    await usuario.click(screen.getByRole("button", { name: /1 · Pergunta para pensar/ }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Confira com o pesquisador e tente de novo/);
  });
});

describe("retomada da sessão", () => {
  it("volta para o problema em que o estudante parou depois de recarregar", async () => {
    localStorage.setItem("adia.sessao", "s1");
    const fetch = vi.fn((_url: string) => respostaJson(estado({ etapa: "linha_de_base", com_ia: false, ciclo: 0 })));
    vi.stubGlobal("fetch", fetch);
    render(<App />);
    expect(await screen.findByText("Resolva 2x + 3 = 11.")).toBeTruthy();
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/sessoes/s1");
  });

  it("esquece a sessão que o servidor não conhece", async () => {
    localStorage.setItem("adia.sessao", "velha");
    vi.stubGlobal("fetch", vi.fn((url: string) =>
      url.endsWith("/saude") ? respostaJson({ ia_disponivel: true, modelo: "m" }) : respostaJson({ detail: "Sessão inexistente." }, 404),
    ));
    render(<App />);
    expect(await screen.findByLabelText(/Seu código/)).toBeTruthy();
    expect(localStorage.getItem("adia.sessao")).toBeNull();
  });
});

describe("fim e última parte", () => {
  const encerrada = (retencao: Estado["retencao"]) => estado({ item: null, com_ia: false, retencao });

  it("antes da janela diz quando voltar, sem botão de começar", () => {
    render(
      <Fim
        estado={encerrada({ concluida: false, disponivel: false, abre_em: "2026-11-09T09:00:00+00:00" })}
        aoRetomar={() => {}}
        aoSair={() => {}}
      />,
    );
    expect(screen.getByText(/A última parte abre em/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Começar a última parte/ })).toBeNull();
  });

  it("dentro da janela oferece a última parte e abre pela API", async () => {
    const usuario = userEvent.setup();
    const fetch = vi.fn((_url: string, _init?: RequestInit) =>
      respostaJson(estado({ etapa: "teste_retencao", com_ia: false, ciclo: 3 })),
    );
    vi.stubGlobal("fetch", fetch);
    const aoRetomar = vi.fn();
    render(
      <Fim
        estado={encerrada({ concluida: false, disponivel: true, abre_em: "2026-11-09T09:00:00+00:00" })}
        aoRetomar={aoRetomar}
        aoSair={() => {}}
      />,
    );
    await usuario.click(screen.getByRole("button", { name: "Começar a última parte" }));
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/sessoes/s1/retencao");
    expect(aoRetomar).toHaveBeenCalledOnce();
  });

  it("depois da última parte só agradece", () => {
    render(<Fim estado={encerrada({ concluida: true, disponivel: true, abre_em: null })} aoRetomar={() => {}} aoSair={() => {}} />);
    expect(screen.getByRole("heading").textContent).toBe("Pronto, você terminou!");
  });
});

describe("projeto STEAM", () => {
  const projeto = estado({
    etapa: "projeto_steam",
    com_ia: false,
    ciclo: 3,
    item: null,
    steam: {
      titulo: "A cisterna da horta",
      enunciado: "A cisterna comporta 1800 litros.",
      partes: [
        { parte: "retirada", pergunta: "Quanto sai por dia?", unidade: "litros", tamanho_max: 40 },
        { parte: "metros", pergunta: "Quantos metros?", unidade: "metros", tamanho_max: 40 },
      ],
      justificativa: { pergunta: "Explique sua recomendação.", tamanho_max: 2000 },
    },
  });

  it("o App abre o projeto quando a sessão chega nele", async () => {
    localStorage.setItem("adia.sessao", "s1");
    vi.stubGlobal("fetch", vi.fn(() => respostaJson(projeto)));
    render(<App />);
    expect(await screen.findByText("A cisterna da horta")).toBeTruthy();
    expect(screen.getByText("Sem dicas nesta parte: resolva sozinho.")).toBeTruthy();
  });

  it("só envia com todas as partes e a justificativa, e manda tudo para a API", async () => {
    const usuario = userEvent.setup();
    const fetch = vi.fn((_url: string, _init?: RequestInit) => respostaJson(estado({ item: null })));
    vi.stubGlobal("fetch", fetch);
    const aoAvancar = vi.fn();
    render(<Steam estado={projeto} aoAvancar={aoAvancar} />);
    const enviar = screen.getByRole("button", { name: "Enviar o projeto" }) as HTMLButtonElement;
    await usuario.type(screen.getByLabelText(/Quanto sai por dia/), "620");
    await usuario.type(screen.getByLabelText(/Explique sua recomendação/), "Regar metade.");
    expect(enviar.disabled).toBe(true);
    await usuario.type(screen.getByLabelText(/Quantos metros/), "18");
    await usuario.click(enviar);
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/sessoes/s1/steam");
    expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({
      partes: { retirada: "620", metros: "18" },
      justificativa: "Regar metade.",
    });
    expect(aoAvancar).toHaveBeenCalledOnce();
  });
});

describe("correção do professor", () => {
  const submissao = {
    id: 7,
    cenario: "A cisterna da horta",
    criado_em: "2026-11-03T12:00:00+00:00",
    avaliadores: [],
    pergunta: "Explique.",
    justificativa: "Regar metade dos canteiros.",
    rubrica: {
      titulo: "Modelagem",
      descricao: "d",
      criterios: [
        {
          criterio: "adequacao_do_modelo",
          descricao: "Traduz a situação.",
          niveis: [
            { nivel: "ausente", pontos: 0, descricao: "Não traduz." },
            { nivel: "exemplar", pontos: 3, descricao: "Traduz bem." },
          ],
        },
      ],
    },
  };

  it("chave errada vira mensagem e não abre a lista", async () => {
    const usuario = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(() => respostaJson({ detail: "Chave do professor incorreta." }, 401)));
    render(<Professor />);
    await usuario.type(screen.getByLabelText("Chave do professor"), "errada");
    await usuario.type(screen.getByLabelText(/código de avaliador/), "prof-01");
    await usuario.click(screen.getByRole("button", { name: "Entrar" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Chave do professor incorreta.");
  });

  it("lista sem participante nem condição, avalia todos os critérios e manda a chave", async () => {
    const usuario = userEvent.setup();
    const fetch = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") return respostaJson({ pontos: 3, pontos_maximos: 3 });
      if (url.endsWith("/submissoes/7")) return respostaJson(submissao);
      return respostaJson([{ id: 7, cenario: submissao.cenario, criado_em: submissao.criado_em, avaliadores: [] }]);
    });
    vi.stubGlobal("fetch", fetch);
    render(<Professor />);
    await usuario.type(screen.getByLabelText("Chave do professor"), "segredo");
    await usuario.type(screen.getByLabelText(/código de avaliador/), "prof-01");
    await usuario.click(screen.getByRole("button", { name: "Entrar" }));
    await usuario.click(await screen.findByRole("button", { name: "Avaliar" }));
    expect(await screen.findByText("Regar metade dos canteiros.")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/P-\d{4}|condição/);
    const gravar = screen.getByRole("button", { name: "Gravar avaliação como PROF-01" }) as HTMLButtonElement;
    expect(gravar.disabled).toBe(true);
    await usuario.click(screen.getByLabelText(/exemplar · 3 pontos/));
    await usuario.click(gravar);
    expect((await screen.findByRole("status")).textContent).toBe("Avaliação 7 gravada: 3 de 3 pontos.");
    const post = fetch.mock.calls.find(([, init]) => init?.method === "POST");
    expect(post?.[0]).toBe("/api/professor/submissoes/7/avaliacoes");
    expect((post?.[1]?.headers as Record<string, string>)["X-Chave-Professor"]).toBe("segredo");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ avaliador: "PROF-01", niveis: { adequacao_do_modelo: "exemplar" } });
  });
});
