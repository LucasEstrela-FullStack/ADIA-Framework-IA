import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Estado } from "../api/cliente";
import { App } from "../App";
import { Item } from "../paginas/Item";

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
