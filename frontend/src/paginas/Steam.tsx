import { useState, type FormEvent } from "react";
import { api, type Estado } from "../api/cliente";

type Props = { estado: Estado; aoAvancar: (estado: Estado) => void };

export function Steam({ estado, aoAvancar }: Props) {
  const projeto = estado.steam!;
  const [respostas, setRespostas] = useState<Record<string, string>>({});
  const [justificativa, setJustificativa] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      aoAvancar(await api.steam(estado.id, respostas, justificativa));
    } catch (e) {
      setErro((e as Error).message);
      setEnviando(false);
    }
  }

  const podeEnviar =
    !enviando && projeto.partes.every((p) => (respostas[p.parte] ?? "").trim() !== "") && justificativa.trim() !== "";

  return (
    <main className="pagina">
      <header className="barra">
        <strong>Projeto final</strong>
        <span className="sutil">uma situação nova com o que você praticou</span>
      </header>

      <section className="cartao" aria-labelledby="titulo-projeto">
        <h2 id="titulo-projeto">{projeto.titulo}</h2>
        <p className="enunciado">{projeto.enunciado}</p>
      </section>

      <p className="selo desligado">Sem dicas nesta parte: resolva sozinho.</p>

      <form className="cartao" onSubmit={enviar}>
        {projeto.partes.map((parte, i) => (
          <label key={parte.parte} className="campo">
            <span>
              <strong>Parte {i + 1}.</strong> {parte.pergunta}
            </span>
            <input
              value={respostas[parte.parte] ?? ""}
              onChange={(e) => setRespostas((anteriores) => ({ ...anteriores, [parte.parte]: e.target.value }))}
              maxLength={parte.tamanho_max}
              placeholder={parte.unidade ?? undefined}
              required
            />
          </label>
        ))}
        <label className="campo">
          <span className="enunciado">{projeto.justificativa.pergunta}</span>
          <textarea
            value={justificativa}
            onChange={(e) => setJustificativa(e.target.value)}
            maxLength={projeto.justificativa.tamanho_max}
            rows={8}
            required
          />
          <span className="sutil">
            {justificativa.length} de {projeto.justificativa.tamanho_max} caracteres
          </span>
        </label>
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button className="primario" disabled={!podeEnviar}>
          Enviar o projeto
        </button>
      </form>
    </main>
  );
}
