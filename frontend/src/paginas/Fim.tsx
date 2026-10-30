export function Fim({ aoSair }: { aoSair: () => void }) {
  return (
    <main className="pagina">
      <header>
        <h1>Pronto, você terminou!</h1>
        <p>Obrigado por participar. Suas respostas foram guardadas.</p>
        <p className="sutil">Avise o pesquisador que você acabou.</p>
      </header>
      <button className="primario" onClick={aoSair}>
        Sair
      </button>
    </main>
  );
}
