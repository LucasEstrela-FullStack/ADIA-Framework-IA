import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Professor } from "./paginas/Professor";
import "./estilo.css";

// A correção do professor mora em /#professor: o servidor só serve o index.html na raiz.
// A tela é escolhida no carregamento; trocar o hash na mesma aba recarrega para trocá-la.
window.addEventListener("hashchange", () => window.location.reload());
createRoot(document.getElementById("raiz")!).render(
  <StrictMode>{window.location.hash === "#professor" ? <Professor /> : <App />}</StrictMode>,
);
