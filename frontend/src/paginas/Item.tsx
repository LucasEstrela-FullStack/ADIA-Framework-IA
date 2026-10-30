import { useState, type FormEvent } from "react";
import { api, type Dica, type Estado } from "../api/cliente";

const ETAPAS: Record<string, string> = {
  linha_de_base: "Aquecimento",
  pratica_assistida: "Prática com dicas",
  desafio_independente: "Desafio sem dicas",
};

const NIVEIS = [
  { nivel: 1, nome: "Pergunta para pensar" },
  { nivel: 2, nome: "Ideia-chave" },
  { nivel: 3, nome: "Primeiro passo" },
  { nivel: 4, nome: "Exemplo parecido" },
];

const ESCALA = Array.from({ length: 11 }, (_, i) => i);

type Props = {
  estado: Estado;
  cicloConcluido: number | null;
  aoAvancar: (estado: Estado, cicloConcluido: number | null) => void;
};

export function Item({ estado, cicloConcluido, aoAvancar }: Props) {
  const [resposta, setResposta] = useState("");
  // Sem valor inicial: um 5 pré-marcado entraria no viés como se o estudante o tivesse escolhido.
  const [confianca, setConfianca] = useState<number | null>(null);
  const [explicacao, setExplicacao] = useState("");
  const [justificativa, setJustificativa] = useState("");
  const [dicas, setDicas] = useState<Dica[]>([]);
  const [carregando, setCarregando] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const item = estado.item!;
  const exigeExplicacao = estado.onloading && estado.dicas_usadas.length === 0 && dicas.length === 0;

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
    if (confianca === null) return;
    setErro(null);
    setEnviando(true);
    try {
      const r = await api.responder(estado.id, resposta, confianca, justificativa);
      aoAvancar(r.estado, r.ciclo_concluido);
    } catch (e) {
      setErro((e as Error).message);
      setEnviando(false);
    }
  }

  const podeEnviar =
    !enviando &&
    carregando === null &&
    resposta.trim() !== "" &&
    confianca !== null &&
    (!estado.justificativa_exigida || justificativa.trim() !== "");

  return (
    <main className="pagina">
      <header className="barra">
        <span>
          <strong>{ETAPAS[estado.etapa] ?? estado.etapa}</strong>
          {estado.ciclo > 0 && <span className="sutil"> · rodada {estado.ciclo} de 3</span>}
        </span>
        <span className="sutil">
          {estado.restantes} {estado.restantes === 1 ? "problema restante" : "problemas restantes"}
        </span>
      </header>

      {cicloConcluido !== null && (
        <p className="cartao destaque" role="status">
          Você terminou a rodada {cicloConcluido} de 3. Vamos para a próxima.
        </p>
      )}

      <section className="cartao" aria-labelledby="titulo-problema">
        <h2 id="titulo-problema">Problema</h2>
        <p className="enunciado">{item.enunciado}</p>
      </section>

      {estado.com_ia ? (
        <section className="cartao" aria-labelledby="titulo-dicas">
          <h2 id="titulo-dicas">Dicas</h2>
          <p className="sutil">Nesta rodada você pode usar as dicas até o nível {estado.teto}.</p>
          {exigeExplicacao && (
            <label className="campo">
              Antes da primeira dica, conte o que você já tentou
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
              >
                {nivel} · {nome}
              </button>
            ))}
          </div>
          <div aria-live="polite">
            {carregando !== null && (
              <p className="sutil" role="status">
                Preparando a dica… pode levar alguns segundos.
              </p>
            )}
            {[...dicas]
              .sort((a, b) => a.nivel - b.nivel)
              .map((d) => (
                <blockquote key={d.nivel} className="dica">
                  <span className="sutil">Dica {d.nivel}</span>
                  <p>{d.texto}</p>
                </blockquote>
              ))}
          </div>
        </section>
      ) : (
        <p className="selo desligado">Sem dicas nesta parte: resolva sozinho.</p>
      )}

      <form className="cartao" onSubmit={enviar}>
        <label className="campo">
          Sua resposta
          <input
            value={resposta}
            onChange={(e) => setResposta(e.target.value)}
            maxLength={item.tamanho_max}
            autoFocus
            required
          />
        </label>
        {estado.justificativa_exigida && (
          <label className="campo">
            Conte como você chegou a essa resposta
            <textarea value={justificativa} onChange={(e) => setJustificativa(e.target.value)} rows={3} required />
          </label>
        )}
        <fieldset className="campo escala">
          <legend>Quanto você está seguro da sua resposta?</legend>
          <div className="opcoes-escala">
            {ESCALA.map((valor) => (
              <label key={valor} className="opcao-escala">
                <input
                  type="radio"
                  name="confianca"
                  value={valor}
                  checked={confianca === valor}
                  onChange={() => setConfianca(valor)}
                  required
                />
                <span>{valor}</span>
              </label>
            ))}
          </div>
          <div className="pontas sutil" aria-hidden="true">
            <span>0 = nada seguro</span>
            <span>10 = totalmente seguro</span>
          </div>
        </fieldset>
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button className="primario" disabled={!podeEnviar}>
          Enviar resposta
        </button>
      </form>
    </main>
  );
}
