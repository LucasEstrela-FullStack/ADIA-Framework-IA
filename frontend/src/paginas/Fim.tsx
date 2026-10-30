import { useState } from "react";
import { api, type Estado } from "../api/cliente";

type Props = { estado: Estado; aoRetomar: (estado: Estado) => void; aoSair: () => void };

function dataLocal(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "long", timeStyle: "short" });
}

export function Fim({ estado, aoRetomar, aoSair }: Props) {
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const retencao = estado.retencao;

  async function comecarUltimaParte() {
    setErro(null);
    setEnviando(true);
    try {
      aoRetomar(await api.iniciarRetencao(estado.id));
    } catch (e) {
      setErro((e as Error).message);
      setEnviando(false);
    }
  }

  if (retencao && !retencao.concluida && retencao.disponivel) {
    return (
      <main className="pagina">
        <header>
          <h1>Que bom ter você de volta!</h1>
          <p>Falta a última parte: alguns problemas para resolver sozinho, sem dicas.</p>
        </header>
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button className="primario" onClick={comecarUltimaParte} disabled={enviando}>
          Começar a última parte
        </button>
      </main>
    );
  }

  const falta = retencao && !retencao.concluida && retencao.abre_em;
  return (
    <main className="pagina">
      <header>
        <h1>{falta ? "Por hoje é só!" : "Pronto, você terminou!"}</h1>
        <p>Obrigado por participar. Suas respostas foram guardadas.</p>
        {falta ? (
          <p>
            A última parte abre em <strong>{dataLocal(retencao.abre_em!)}</strong>. Volte nesse dia e entre com o mesmo
            código.
          </p>
        ) : (
          <p className="sutil">Avise o pesquisador que você acabou.</p>
        )}
      </header>
      <button className="primario" onClick={aoSair}>
        Sair
      </button>
    </main>
  );
}
