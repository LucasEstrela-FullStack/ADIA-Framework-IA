import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type Estado, type Saude } from "../api/cliente";

// A condição experimental é sorteada pelo servidor (DO-07) e não aparece aqui: o estudante
// não escolhe nem vê em que grupo está.
export function Inicio({ aoComecar }: { aoComecar: (estado: Estado) => void }) {
  const [codigo, setCodigo] = useState("");
  const [saude, setSaude] = useState<Saude | null>(null);
  const [semSistema, setSemSistema] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const verificar = useCallback(() => {
    setSemSistema(false);
    api.saude().then(setSaude, () => setSemSistema(true));
  }, []);

  useEffect(verificar, [verificar]);

  async function comecar(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      aoComecar(await api.iniciar(codigo.trim().toUpperCase()));
    } catch (e) {
      setErro((e as Error).message);
      setEnviando(false);
    }
  }

  return (
    <main className="pagina">
      <header>
        <h1>Vamos resolver alguns problemas</h1>
        <p className="sutil">
          Primeiro você resolve sozinho. Depois pratica com dicas e, no fim de cada rodada, resolve outros problemas
          sem ajuda.
        </p>
      </header>
      <form className="cartao" onSubmit={comecar}>
        <label className="campo">
          Seu código (o pesquisador entrega, por exemplo P-0001)
          <input
            value={codigo}
            onChange={(e) => setCodigo(e.target.value)}
            pattern="[Pp]-[0-9]{4}"
            autoComplete="off"
            autoFocus
            required
          />
        </label>
        {saude && !saude.ia_disponivel && <p className="sutil">As dicas vão usar textos prontos hoje.</p>}
        {semSistema && (
          <p className="erro" role="alert">
            O sistema ainda não está pronto. Avise o pesquisador.{" "}
            <button type="button" onClick={verificar}>
              Tentar de novo
            </button>
          </p>
        )}
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button className="primario" disabled={enviando || saude === null || !codigo.trim()}>
          Começar
        </button>
      </form>
    </main>
  );
}
