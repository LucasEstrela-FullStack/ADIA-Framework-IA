import type { Estado } from "../api/cliente";
import { porcento } from "./formato";

const COLUNAS = ["Ciclo", "Teto", "TAI", "Com IA", "TT", "Confiança", "DSS", "IIC", "Decisão", "Teto seguinte"];

export function Resultados({ estado, aoReiniciar }: { estado: Estado; aoReiniciar: () => void }) {
  return (
    <main className="pagina">
      <header>
        <h1>Sessão concluída</h1>
        <p className="sutil">
          Condição {estado.condicao}. TAI é o acerto sem IA. IIC compara o acerto sem IA com o acerto com IA e deve ser
          lido ao lado da TAI.
        </p>
      </header>
      <div className="tabela">
        <table>
          <thead>
            <tr>
              {COLUNAS.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {estado.ciclos.map((c) => (
              <tr key={c.ciclo}>
                <td>{c.ciclo}</td>
                <td>{c.teto}</td>
                <td>{porcento(c.tai)}</td>
                <td>{porcento(c.acerto_assistido)}</td>
                <td>{porcento(c.transferencia)}</td>
                <td>{porcento(c.confianca)}</td>
                <td>{porcento(c.dss)}</td>
                <td>{porcento(c.iic)}</td>
                <td>{c.decisao}</td>
                <td>{c.teto_seguinte}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button className="primario" onClick={aoReiniciar}>
        Nova sessão
      </button>
    </main>
  );
}
