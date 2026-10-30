import { useEffect, useState } from "react";
import { api, ErroDaApi, type Estado } from "./api/cliente";
import { Fim } from "./paginas/Fim";
import { Inicio } from "./paginas/Inicio";
import { Item } from "./paginas/Item";

const CHAVE_DA_SESSAO = "adia.sessao";

// O id da sessão sobrevive a F5 e a aba fechada: o servidor reconstrói a sessão pelos eventos.
function lerSessaoGuardada(): string | null {
  try {
    return localStorage.getItem(CHAVE_DA_SESSAO);
  } catch {
    return null;
  }
}

function guardarSessao(id: string | null) {
  try {
    if (id === null) localStorage.removeItem(CHAVE_DA_SESSAO);
    else localStorage.setItem(CHAVE_DA_SESSAO, id);
  } catch {
    // Sem armazenamento local a sessão só não sobrevive ao recarregar.
  }
}

export function App() {
  const [estado, setEstado] = useState<Estado | null>(null);
  const [cicloConcluido, setCicloConcluido] = useState<number | null>(null);
  const [retomando, setRetomando] = useState(() => lerSessaoGuardada() !== null);

  useEffect(() => {
    const guardada = lerSessaoGuardada();
    if (guardada === null) return;
    api
      .ler(guardada)
      .then(setEstado, (erro: unknown) => {
        if (erro instanceof ErroDaApi && erro.status === 404) guardarSessao(null);
      })
      .finally(() => setRetomando(false));
  }, []);

  function comecar(novo: Estado) {
    guardarSessao(novo.id);
    setEstado(novo);
  }

  if (retomando) return <main className="pagina" aria-busy="true" />;
  if (estado === null) return <Inicio aoComecar={comecar} />;
  if (estado.item === null) {
    return (
      <Fim
        aoSair={() => {
          guardarSessao(null);
          setEstado(null);
        }}
      />
    );
  }
  return (
    <Item
      key={estado.item.id}
      estado={estado}
      cicloConcluido={cicloConcluido}
      aoAvancar={(novo, ciclo) => {
        setCicloConcluido(ciclo);
        setEstado(novo);
      }}
    />
  );
}
