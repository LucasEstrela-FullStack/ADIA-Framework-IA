import { useState } from "react";
import type { Ciclo, Estado } from "./api/cliente";
import { Inicio } from "./paginas/Inicio";
import { Item } from "./paginas/Item";
import { Resultados } from "./paginas/Resultados";

export function App() {
  const [estado, setEstado] = useState<Estado | null>(null);
  const [cicloFechado, setCicloFechado] = useState<Ciclo | null>(null);

  if (estado === null) return <Inicio aoComecar={setEstado} />;
  if (estado.item === null) return <Resultados estado={estado} aoReiniciar={() => setEstado(null)} />;
  return (
    <Item
      key={estado.item.id}
      estado={estado}
      cicloFechado={cicloFechado}
      aoAvancar={(novo, ciclo) => {
        setCicloFechado(ciclo);
        setEstado(novo);
      }}
    />
  );
}
