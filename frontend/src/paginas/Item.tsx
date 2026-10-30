import { useState, type FormEvent } from "react";
import { api, type Ciclo, type Dica, type Estado } from "../api/cliente";
import { porcento } from "./formato";

const ETAPAS: Record<string, string> = {
  linha_de_base: "Linha de base",
  pratica_assistida: "Prática assistida",
  desafio_independente: "Desafio independente",
};

const NIVEIS = [
  { nivel: 1, nome: "L1 · Pergunta" },
  { nivel: 2, nome: "L2 · Conceito" },
  { nivel: 3, nome: "L3 · Primeiro passo" },
  { nivel: 4, nome: "L4 · Exemplo" },
];

const DECISOES: Record<string, string> = {
  fading: "Fading: o teto de ajuda desce um nível.",
  onloading: "Onloading: explique o que tentou antes de pedir dica.",
  escalonar: "Escalonar: o teto de ajuda sobe um nível.",
  manter: "Manter: o teto de ajuda fica igual.",
};

type Props = { estado: Estado; cicloFechado: Ciclo | null; aoAvancar: (estado: Estado, ciclo: Ciclo | null) => void };

export function Item({ estado, cicloFechado, aoAvancar }: Props) {
  const [resposta, setResposta] = useState("");
  const [confianca, setConfianca] = useState(5);
  const [explicacao, setExplicacao] = useState("");
  const [justificativa, setJustificativa] = useState("");
  const [dicas, setDicas] = useState<Dica[]>([]);
  const [carregando, setCarregando] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const item = estado.item!;
  const exigeExplicacao = estado.onloading && dicas.length === 0;

  async function pedirDica(nivel: number) {
    setErro(null);
    setCarregando(nivel);
    try {
      const dica = await api.dica(estado.id, nivel, explicacao);
      setDicas((anteriores) => [...anteriores.filter((d) => d.nivel !== nivel), dica]);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setCarregando(null);
    }
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const r = await api.responder(estado.id, resposta, confianca, justificativa);
      aoAvancar(r.estado, r.ciclo_fechado);
    } catch (e) {
      setErro((e as Error).message);
      setEnviando(false);
    }
  }

  return (
    <main className="pagina">
      <header className="barra">
        <span>
          <strong>{ETAPAS[estado.etapa] ?? estado.etapa}</strong>
          {estado.ciclo > 0 && <span className="sutil"> · ciclo {estado.ciclo} de 3</span>}
        </span>
        <span className="sutil">
          {estado.restantes} {estado.restantes === 1 ? "item restante" : "itens restantes"}
        </span>
      </header>

      {cicloFechado && (
        <section className="cartao destaque" aria-live="polite">
          <strong>Fim do ciclo {cicloFechado.ciclo}.</strong> Acerto sem IA {porcento(cicloFechado.tai)}, com IA{" "}
          {porcento(cicloFechado.acerto_assistido)}. {DECISOES[cicloFechado.decisao]}
        </section>
      )}

      {estado.com_ia ? (
        <p className="selo">IA disponível · teto de ajuda L{estado.teto}</p>
      ) : (
        <p className="selo desligado">IA desativada nesta etapa</p>
      )}

      <section className="cartao">
        <p className="enunciado">{item.enunciado}</p>
      </section>

      {estado.com_ia && (
        <section className="cartao">
          <h2>Dicas</h2>
          {exigeExplicacao && (
            <label className="campo">
              Antes da primeira dica, explique o que você já tentou
              <textarea
                value={explicacao}
                onChange={(e) => setExplicacao(e.target.value)}
                rows={2}
                maxLength={500}
              />
            </label>
          )}
          <div className="dicas">
            {NIVEIS.map(({ nivel, nome }) => (
              <button
                key={nivel}
                type="button"
                onClick={() => pedirDica(nivel)}
                disabled={nivel > estado.teto || carregando !== null || (exigeExplicacao && !explicacao.trim())}
                title={nivel > estado.teto ? "Acima do teto de ajuda deste ciclo" : undefined}
              >
                {carregando === nivel ? "Gerando…" : nome}
              </button>
            ))}
          </div>
          {[...dicas]
            .sort((a, b) => a.nivel - b.nivel)
            .map((d) => (
              <blockquote key={d.nivel} className="dica">
                <span className="sutil">
                  L{d.nivel} · {d.origem === "ia" ? "IA local" : "texto revisado"}
                </span>
                <p>{d.texto}</p>
              </blockquote>
            ))}
        </section>
      )}

      <form className="cartao" onSubmit={enviar}>
        <label className="campo">
          Sua resposta
          <input value={resposta} onChange={(e) => setResposta(e.target.value)} autoFocus required />
        </label>
        {estado.justificativa_exigida && (
          <label className="campo">
            Conte como você chegou a essa resposta
            <textarea value={justificativa} onChange={(e) => setJustificativa(e.target.value)} rows={3} required />
          </label>
        )}
        <label className="campo">
          <span>
            Confiança na resposta: <strong>{confianca}</strong> de 10
          </span>
          <input
            type="range"
            min={0}
            max={10}
            value={confianca}
            onChange={(e) => setConfianca(Number(e.target.value))}
          />
        </label>
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button
          className="primario"
          disabled={
            enviando ||
            carregando !== null ||
            !resposta.trim() ||
            (estado.justificativa_exigida && !justificativa.trim())
          }
        >
          Enviar resposta
        </button>
      </form>
    </main>
  );
}
