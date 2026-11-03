import { useState, type FormEvent } from "react";
import { professor, type ResumoDaSubmissao, type Submissao } from "../api/cliente";

// Só na aba: a máquina é a mesma dos estudantes, e a chave não deve sobreviver a ela.
function lerGuardado(nome: string): string {
  try {
    return sessionStorage.getItem(nome) ?? "";
  } catch {
    return "";
  }
}

function guardar(nome: string, valor: string) {
  try {
    sessionStorage.setItem(nome, valor);
  } catch {
    // Sem armazenamento, a chave é pedida de novo ao recarregar.
  }
}

function dataLocal(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function Professor() {
  const [chave, setChave] = useState(() => lerGuardado("adia.professor.chave"));
  const [avaliador, setAvaliador] = useState(() => lerGuardado("adia.professor.avaliador"));
  const [lista, setLista] = useState<ResumoDaSubmissao[] | null>(null);
  const [aberta, setAberta] = useState<Submissao | null>(null);
  const [niveis, setNiveis] = useState<Record<string, string>>({});
  const [aviso, setAviso] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function carregar(evento?: FormEvent) {
    evento?.preventDefault();
    setErro(null);
    setOcupado(true);
    try {
      setLista(await professor.submissoes(chave));
      guardar("adia.professor.chave", chave);
      guardar("adia.professor.avaliador", avaliador);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setOcupado(false);
    }
  }

  async function abrir(id: number) {
    setErro(null);
    setAviso(null);
    try {
      setAberta(await professor.submissao(chave, id));
      setNiveis({});
    } catch (e) {
      setErro((e as Error).message);
    }
  }

  async function avaliar(evento: FormEvent) {
    evento.preventDefault();
    if (aberta === null) return;
    setErro(null);
    setOcupado(true);
    try {
      const nota = await professor.avaliar(chave, aberta.id, avaliador, niveis);
      setAviso(`Avaliação ${aberta.id} gravada: ${nota.pontos} de ${nota.pontos_maximos} pontos.`);
      setAberta(null);
      setLista(await professor.submissoes(chave));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setOcupado(false);
    }
  }

  const mensagemDeErro = erro && (
    <p className="erro" role="alert">
      {erro}
    </p>
  );

  if (lista === null) {
    return (
      <main className="pagina">
        <header>
          <h1>Correção do projeto STEAM</h1>
          <p className="sutil">Gere a chave com o pesquisador: uv run adia professor chave.</p>
        </header>
        <form className="cartao" onSubmit={carregar}>
          <label className="campo">
            Chave do professor
            <input type="password" value={chave} onChange={(e) => setChave(e.target.value)} required />
          </label>
          <label className="campo">
            Seu código de avaliador (PROF-01 a PROF-99)
            <input
              value={avaliador}
              onChange={(e) => setAvaliador(e.target.value.toUpperCase())}
              pattern="PROF-[0-9]{2}"
              required
            />
          </label>
          {mensagemDeErro}
          <button className="primario" disabled={ocupado}>
            Entrar
          </button>
        </form>
      </main>
    );
  }

  if (aberta !== null) {
    const completa = aberta.rubrica.criterios.every((c) => niveis[c.criterio] !== undefined);
    return (
      <main className="pagina">
        <header className="barra">
          <strong>Submissão {aberta.id}</strong>
          <span className="sutil">{aberta.cenario}</span>
        </header>
        {aberta.pergunta && (
          <section className="cartao" aria-labelledby="titulo-pedido">
            <h2 id="titulo-pedido">O que foi pedido</h2>
            <p className="enunciado">{aberta.pergunta}</p>
          </section>
        )}
        <section className="cartao" aria-labelledby="titulo-justificativa">
          <h2 id="titulo-justificativa">Justificativa do estudante</h2>
          <p className="enunciado">{aberta.justificativa}</p>
        </section>
        <form className="cartao" onSubmit={avaliar}>
          <h2>{aberta.rubrica.titulo}</h2>
          {aberta.rubrica.criterios.map((criterio) => (
            <fieldset key={criterio.criterio} className="campo">
              <legend>
                <strong>{criterio.criterio.replaceAll("_", " ")}</strong>
              </legend>
              <p className="sutil">{criterio.descricao}</p>
              {criterio.niveis.map((nivel) => (
                <label key={nivel.nivel} className="opcao">
                  <input
                    type="radio"
                    name={criterio.criterio}
                    checked={niveis[criterio.criterio] === nivel.nivel}
                    onChange={() => setNiveis((anteriores) => ({ ...anteriores, [criterio.criterio]: nivel.nivel }))}
                    required
                  />
                  <span>
                    <strong>
                      {nivel.nivel} · {nivel.pontos} {nivel.pontos === 1 ? "ponto" : "pontos"}
                    </strong>
                    <span className="sutil">{nivel.descricao}</span>
                  </span>
                </label>
              ))}
            </fieldset>
          ))}
          {mensagemDeErro}
          <button className="primario" disabled={ocupado || !completa}>
            Gravar avaliação como {avaliador}
          </button>
          <button type="button" onClick={() => setAberta(null)}>
            Voltar à lista
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="pagina">
      <header className="barra">
        <strong>Projetos para corrigir</strong>
        <span className="sutil">avaliando como {avaliador}</span>
      </header>
      {aviso && (
        <p className="cartao destaque" role="status">
          {aviso}
        </p>
      )}
      {mensagemDeErro}
      {lista.length === 0 ? (
        <p className="cartao">Nenhum projeto enviado ainda.</p>
      ) : (
        lista.map((s) => {
          const minha = s.avaliadores.includes(avaliador);
          return (
            <section key={s.id} className="cartao">
              <h2>Submissão {s.id}</h2>
              <p className="sutil">
                {s.cenario} · enviada em {dataLocal(s.criado_em)} ·{" "}
                {s.avaliadores.length ? `avaliada por ${s.avaliadores.join(", ")}` : "sem avaliação"}
              </p>
              <button onClick={() => abrir(s.id)} disabled={minha}>
                {minha ? "Você já avaliou" : "Avaliar"}
              </button>
            </section>
          );
        })
      )}
      <button onClick={() => carregar()} disabled={ocupado}>
        Atualizar lista
      </button>
    </main>
  );
}
