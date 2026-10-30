import { useEffect, useState } from "react";
import { api, type Estado, type Saude } from "../api/cliente";

const CONDICOES = [
  { valor: "B", nome: "B · ADIA", descricao: "O teto de ajuda se ajusta ao seu desempenho sem IA." },
  { valor: "A", nome: "A · Suporte constante", descricao: "Todas as dicas liberadas em todos os ciclos." },
  { valor: "C", nome: "C · Fading fixo", descricao: "O teto desce um nível por ciclo, sem olhar o desempenho." },
];

export function Inicio({ aoComecar }: { aoComecar: (estado: Estado) => void }) {
  const [condicao, setCondicao] = useState("B");
  const [saude, setSaude] = useState<Saude | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api.saude().then(setSaude, () => setErro("A API local não respondeu. Rode scripts/dev-backend.ps1."));
  }, []);

  async function comecar() {
    setEnviando(true);
    try {
      aoComecar(await api.criar(condicao));
    } catch (e) {
      setErro((e as Error).message);
      setEnviando(false);
    }
  }

  return (
    <main className="pagina">
      <header>
        <h1>ADIA · CognitiveLoop</h1>
        <p className="sutil">
          Linha de base sem IA, três ciclos de prática com dicas e desafio independente. Só o desempenho sem IA conta
          para reduzir a ajuda.
        </p>
      </header>
      <fieldset className="cartao">
        <legend>Condição experimental</legend>
        {CONDICOES.map((c) => (
          <label key={c.valor} className="opcao">
            <input
              type="radio"
              name="condicao"
              value={c.valor}
              checked={condicao === c.valor}
              onChange={() => setCondicao(c.valor)}
            />
            <span>
              <strong>{c.nome}</strong>
              <span className="sutil">{c.descricao}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {saude && (
        <p className={saude.ia_disponivel ? "sutil" : "aviso"}>
          {saude.ia_disponivel
            ? `IA local pronta: ${saude.modelo}.`
            : `IA local indisponível (${saude.modelo}). As dicas usarão o texto pré-escrito.`}
        </p>
      )}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <button className="primario" onClick={comecar} disabled={enviando || saude === null}>
        Começar sessão
      </button>
    </main>
  );
}
