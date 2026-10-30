"""Repositório SQLite: participantes, sessões, eventos, decisões por ciclo e exclusões.

A sessão não é gravada como fotografia: ela é reconstruída reaplicando os eventos em
ordem (``Servico.obter``), e as decisões gravadas servem de conferência do replay. Uma
conexão por operação, porque a API atende rotas síncronas em várias threads e o
``sqlite3`` não compartilha conexão entre threads; WAL deixa leitura e escrita concorrentes.
"""

from __future__ import annotations

import random
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import Final, Literal

from adia.nucleo.regulacao.regra import ConjuntoDeLimiares
from adia.nucleo.sessao.gestor import ResumoDoCiclo, Sessao
from adia.tipos import Condicao, Etapa, Indisponivel, Medida, Nivel

BANCO_DE_DADOS: Final = Path("data") / "adia.db"
"""Relativo à raiz do projeto. Fora do git pelo padrão ``*.db``: contém dados de estudante."""

PRAZO_DE_RETENCAO: Final = timedelta(days=180)
"""DO-14."""

CONDICOES_DO_ESTUDO: Final = (Condicao.A, Condicao.B, Condicao.C)

type MotivoDeExclusao = Literal["pedido", "prazo_expirado"]


class ParticipanteDesconhecido(Exception):
    """Código de participante que o pesquisador não cadastrou."""


@dataclass(frozen=True)
class Proveniencia:
    semente_banco: int
    hash_banco_itens: str
    commit_codigo: str | None
    modelo: str
    limiares_versao: str


@dataclass(frozen=True)
class RegistroDeSessao:
    id: str
    participante_id: str
    condicao: Condicao
    semente_atribuicao: int
    proveniencia: Proveniencia
    concluida_em: datetime | None = None
    retencao_iniciada_em: datetime | None = None
    retencao_desvio_horas: str | None = None


@dataclass(frozen=True)
class Evento:
    tipo: str
    etapa: str
    ciclo: int
    item_id: str
    teto: Nivel
    nivel: Nivel | None
    explicacao: str | None
    justificativa: str | None
    acerto: bool | None
    confianca: int | None


@dataclass(frozen=True)
class DecisaoGravada:
    decisao: str
    teto_aplicado: Nivel
    limiares_versao: str


def _agora() -> datetime:
    return datetime.now(UTC)


def _carimbo(instante: datetime) -> str:
    return instante.isoformat(timespec="milliseconds")


def _texto(medida: Medida) -> str | None:
    return None if isinstance(medida, Indisponivel) else str(medida)


def _migracoes() -> list[tuple[int, str]]:
    pasta = files("adia.persistencia") / "migracoes"
    scripts = sorted((p for p in pasta.iterdir() if p.name.endswith(".sql")), key=lambda p: p.name)
    return [(int(p.name.split("_", 1)[0]), p.read_text(encoding="utf-8")) for p in scripts]


def _contexto(sessao: Sessao) -> tuple[str, int, str, int]:
    """Etapa, ciclo, item e teto no momento do evento, antes de a sessão avançar."""
    item = sessao.item_atual
    if item is None or not isinstance(sessao.etapa, Etapa):
        raise ValueError("evento sem item atual: a sessão está encerrada")
    return sessao.etapa.value, sessao.ciclo, item.id, int(sessao.teto)


def sortear_condicao(contagens: dict[Condicao, int], semente: int) -> Condicao:
    """DO-07: sorteio uniforme entre as condições de menor contagem corrente na coorte."""
    menor = min(contagens[c] for c in CONDICOES_DO_ESTUDO)
    candidatas = [c for c in CONDICOES_DO_ESTUDO if contagens[c] == menor]
    return random.Random(semente).choice(candidatas)


class Repositorio:
    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        caminho.parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(caminho, timeout=5)
        try:
            conexao.execute("PRAGMA journal_mode = WAL")
            versao: int = conexao.execute("PRAGMA user_version").fetchone()[0]
            for numero, script in _migracoes():
                if numero > versao:
                    # executescript confirma o que estiver pendente; o BEGIN explícito faz
                    # a migração e o novo user_version entrarem juntos ou não entrarem.
                    conexao.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {numero};\nCOMMIT;")
        finally:
            conexao.close()

    @contextmanager
    def transacao(self) -> Iterator[sqlite3.Connection]:
        """Transação imediata: confirma ao sair sem erro; desfaz se o bloco levantar.

        ``BEGIN IMMEDIATE`` reserva a escrita na entrada, o que serializa a contagem e a
        inserção da atribuição balanceada entre processos.
        """
        conexao = sqlite3.connect(self.caminho, timeout=5, isolation_level=None)
        try:
            conexao.execute("PRAGMA foreign_keys = ON")
            conexao.execute("BEGIN IMMEDIATE")
            try:
                yield conexao
            except BaseException:
                conexao.execute("ROLLBACK")
                raise
            conexao.execute("COMMIT")
        finally:
            conexao.close()

    # ------------------------------------------------------------------ participantes

    def criar_participantes(self, coorte: str, quantidade: int) -> list[str]:
        """Cadastra ``quantidade`` pseudônimos novos na coorte e devolve os códigos."""
        if not coorte.strip() or quantidade < 1:
            raise ValueError("coorte não vazia e quantidade positiva")
        with self.transacao() as conexao:
            ultimo = conexao.execute("SELECT max(id) FROM participante").fetchone()[0]
            inicio = 1 if ultimo is None else int(ultimo[2:]) + 1
            if inicio + quantidade - 1 > 9999:
                raise ValueError("limite de 9999 participantes")
            codigos = [f"P-{n:04d}" for n in range(inicio, inicio + quantidade)]
            agora = _carimbo(_agora())
            conexao.executemany(
                "INSERT INTO participante (id, coorte, criado_em) VALUES (?, ?, ?)",
                [(codigo, coorte.strip(), agora) for codigo in codigos],
            )
        return codigos

    def sessao_do_participante(self, participante_id: str) -> str | None:
        """Sessão já aberta do participante, ou ``None``. Levanta se o código não existe."""
        with self.transacao() as conexao:
            if conexao.execute("SELECT 1 FROM participante WHERE id = ?", (participante_id,)).fetchone() is None:
                raise ParticipanteDesconhecido(participante_id)
            linha = conexao.execute("SELECT id FROM sessao WHERE participante_id = ?", (participante_id,)).fetchone()
        return None if linha is None else str(linha[0])

    # ------------------------------------------------------------------ sessões

    def criar_sessao(
        self, sessao_id: str, participante_id: str, semente_atribuicao: int, proveniencia: Proveniencia
    ) -> RegistroDeSessao:
        """Atribui a condição pela regra de DO-07 e grava a sessão, na mesma transação."""
        with self.transacao() as conexao:
            coorte = conexao.execute("SELECT coorte FROM participante WHERE id = ?", (participante_id,)).fetchone()
            if coorte is None:
                raise ParticipanteDesconhecido(participante_id)
            contagens = dict.fromkeys(CONDICOES_DO_ESTUDO, 0)
            for condicao, total in conexao.execute(
                "SELECT s.condicao, count(*) FROM sessao s JOIN participante p ON p.id = s.participante_id "
                "WHERE p.coorte = ? GROUP BY s.condicao",
                (coorte[0],),
            ):
                contagens[Condicao(condicao)] = total
            condicao = sortear_condicao(contagens, semente_atribuicao)
            conexao.execute(
                "INSERT INTO sessao (id, participante_id, condicao, semente_atribuicao, semente_banco, "
                "hash_banco_itens, commit_codigo, modelo, limiares_versao, criada_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sessao_id,
                    participante_id,
                    condicao.value,
                    semente_atribuicao,
                    proveniencia.semente_banco,
                    proveniencia.hash_banco_itens,
                    proveniencia.commit_codigo,
                    proveniencia.modelo,
                    proveniencia.limiares_versao,
                    _carimbo(_agora()),
                ),
            )
        return RegistroDeSessao(sessao_id, participante_id, condicao, semente_atribuicao, proveniencia)

    def ler_sessao(
        self, sessao_id: str
    ) -> tuple[RegistroDeSessao, list[Evento], dict[int, DecisaoGravada]] | None:
        with self.transacao() as conexao:
            linha = conexao.execute(
                "SELECT participante_id, condicao, semente_atribuicao, semente_banco, hash_banco_itens, "
                "commit_codigo, modelo, limiares_versao, concluida_em, retencao_iniciada_em, retencao_desvio_horas "
                "FROM sessao WHERE id = ?",
                (sessao_id,),
            ).fetchone()
            if linha is None:
                return None
            eventos = conexao.execute(
                "SELECT tipo, etapa, ciclo, item_id, teto, nivel, explicacao, justificativa, acerto, confianca "
                "FROM evento WHERE sessao_id = ? ORDER BY id",
                (sessao_id,),
            ).fetchall()
            decisoes = conexao.execute(
                "SELECT ciclo, decisao, teto_aplicado, limiares_versao FROM decisao_ciclo WHERE sessao_id = ?",
                (sessao_id,),
            ).fetchall()
        registro = RegistroDeSessao(
            id=sessao_id,
            participante_id=linha[0],
            condicao=Condicao(linha[1]),
            semente_atribuicao=linha[2],
            proveniencia=Proveniencia(linha[3], linha[4], linha[5], linha[6], linha[7]),
            concluida_em=None if linha[8] is None else datetime.fromisoformat(linha[8]),
            retencao_iniciada_em=None if linha[9] is None else datetime.fromisoformat(linha[9]),
            retencao_desvio_horas=linha[10],
        )
        return (
            registro,
            [
                Evento(
                    tipo=e[0],
                    etapa=e[1],
                    ciclo=e[2],
                    item_id=e[3],
                    teto=Nivel(e[4]),
                    nivel=None if e[5] is None else Nivel(e[5]),
                    explicacao=e[6],
                    justificativa=e[7],
                    acerto=None if e[8] is None else bool(e[8]),
                    confianca=e[9],
                )
                for e in eventos
            ],
            {d[0]: DecisaoGravada(d[1], Nivel(d[2]), d[3]) for d in decisoes},
        )

    # ------------------------------------------------------------------ limiares

    _CAMPOS_DE_LIMIAR = (
        "independente_fading",
        "gap_maximo",
        "vies_maximo_fading",
        "independente_escalonar",
        "vies_justificativa",
    )

    def limiares(self, versao: str | None = None) -> ConjuntoDeLimiares:
        """A versão pedida, ou a vigente (a mais recente) quando ``versao`` é ``None``."""
        campos = ", ".join(self._CAMPOS_DE_LIMIAR)
        with self.transacao() as conexao:
            if versao is None:
                linha = conexao.execute(
                    f"SELECT versao, {campos} FROM limiares ORDER BY criado_em DESC, rowid DESC LIMIT 1"
                ).fetchone()
            else:
                linha = conexao.execute(f"SELECT versao, {campos} FROM limiares WHERE versao = ?", (versao,)).fetchone()
        if linha is None:
            raise KeyError(f"limiares {versao!r} não existem no banco")
        valores = dict(zip(self._CAMPOS_DE_LIMIAR, (Decimal(v) for v in linha[1:]), strict=True))
        return ConjuntoDeLimiares(**valores, versao=linha[0])

    def definir_limiares(self, mudancas: dict[str, Decimal]) -> ConjuntoDeLimiares:
        """Grava uma versão nova a partir da vigente, com as mudanças pedidas, e a devolve."""
        atual = self.limiares()
        valores = {campo: mudancas.get(campo, getattr(atual, campo)) for campo in self._CAMPOS_DE_LIMIAR}
        if any(not Decimal(0) <= v <= Decimal(1) for v in valores.values()):
            raise ValueError("todo limiar fica entre 0 e 1")
        if valores["independente_escalonar"] >= valores["independente_fading"]:
            raise ValueError("o limiar de escalonar precisa ficar abaixo do de fading")
        with self.transacao() as conexao:
            total = conexao.execute("SELECT count(*) FROM limiares").fetchone()[0]
            versao = f"v{total + 1}"
            conexao.execute(
                "INSERT INTO limiares VALUES (?, ?, ?, ?, ?, ?, ?)",
                (versao, *(str(valores[c]) for c in self._CAMPOS_DE_LIMIAR), _carimbo(_agora())),
            )
        return ConjuntoDeLimiares(**valores, versao=versao)

    def versao_do_esquema(self) -> int:
        with self.transacao() as conexao:
            versao: int = conexao.execute("PRAGMA user_version").fetchone()[0]
        return versao

    def sessoes(self) -> list[tuple[str, str]]:
        """``(sessao_id, criada_em)`` de todas as sessões, em ordem de criação."""
        with self.transacao() as conexao:
            linhas = conexao.execute("SELECT id, criada_em FROM sessao ORDER BY criada_em, id").fetchall()
        return [(str(i), str(c)) for i, c in linhas]

    def eventos_para_exportar(self, sessao_id: str) -> list[dict[str, object]]:
        """Linhas completas do registro, em ordem, com os nomes de coluna do banco."""
        with self.transacao() as conexao:
            cursor = conexao.execute("SELECT * FROM evento WHERE sessao_id = ? ORDER BY id", (sessao_id,))
            nomes = [coluna[0] for coluna in cursor.description]
            return [dict(zip(nomes, linha, strict=True)) for linha in cursor.fetchall()]

    # ------------------------------------------------------------------ eventos

    @staticmethod
    def registrar_dica(
        conexao: sqlite3.Connection,
        sessao_id: str,
        sessao: Sessao,
        nivel: Nivel,
        explicacao: str,
        dica: tuple[str, str, str | None],
    ) -> None:
        """Grava a dica entregue: ``dica`` é (texto, origem, motivo)."""
        conexao.execute(
            "INSERT INTO evento (sessao_id, tipo, etapa, ciclo, item_id, teto, nivel, explicacao, "
            "texto_dica, origem, motivo, criado_em) VALUES (?, 'dica', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sessao_id, *_contexto(sessao), int(nivel), explicacao, *dica, _carimbo(_agora())),
        )

    @staticmethod
    def registrar_resposta(
        conexao: sqlite3.Connection,
        sessao_id: str,
        sessao: Sessao,
        resposta: str,
        justificativa: str,
        acerto: bool | None,
        confianca: int,
    ) -> None:
        conexao.execute(
            "INSERT INTO evento (sessao_id, tipo, etapa, ciclo, item_id, teto, resposta, justificativa, "
            "acerto, confianca, criado_em) VALUES (?, 'resposta', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sessao_id,
                *_contexto(sessao),
                resposta,
                justificativa or None,
                None if acerto is None else int(acerto),
                confianca,
                _carimbo(_agora()),
            ),
        )

    @staticmethod
    def registrar_decisao(
        conexao: sqlite3.Connection, sessao_id: str, resumo: ResumoDoCiclo, condicao: Condicao
    ) -> None:
        """Grava a decisão do ciclo; em A e C ela é sombra (``aplicada = 0``)."""
        decisao = resumo.decisao
        conexao.execute(
            "INSERT INTO decisao_ciclo (sessao_id, ciclo, teto, acerto_assistido, acerto_independente, "
            "confianca, gap, vies, evidencia_incompleta, decisao, teto_indicado, teto_aplicado, aplicada, "
            "limiares_versao, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sessao_id,
                resumo.ciclo,
                int(resumo.teto),
                _texto(resumo.acerto_assistido),
                _texto(resumo.acerto_independente),
                _texto(resumo.confianca),
                _texto(decisao.gap),
                _texto(decisao.vies),
                decisao.evidencia_incompleta,
                decisao.tipo.value,
                int(decisao.teto_resultante),
                int(resumo.teto_seguinte),
                int(condicao is Condicao.B),
                decisao.limiares_versao,
                _carimbo(_agora()),
            ),
        )

    @staticmethod
    def iniciar_retencao(
        conexao: sqlite3.Connection, sessao_id: str, instante: datetime, desvio_horas: str | None
    ) -> None:
        conexao.execute(
            "UPDATE sessao SET retencao_iniciada_em = ?, retencao_desvio_horas = ? WHERE id = ?",
            (_carimbo(instante), desvio_horas, sessao_id),
        )

    @staticmethod
    def concluir_retencao(conexao: sqlite3.Connection, sessao_id: str) -> None:
        """Fim da coleta do participante: o prazo de DO-14 passa a contar daqui."""
        agora = _agora()
        conexao.execute("UPDATE sessao SET retencao_concluida_em = ? WHERE id = ?", (_carimbo(agora), sessao_id))
        conexao.execute(
            "UPDATE participante SET retencao_ate = ? WHERE id = (SELECT participante_id FROM sessao WHERE id = ?)",
            (_carimbo(agora + PRAZO_DE_RETENCAO), sessao_id),
        )

    @staticmethod
    def concluir(conexao: sqlite3.Connection, sessao_id: str) -> None:
        """Marca a conclusão dos ciclos e fixa um prazo provisório (DO-14).

        O prazo provisório conta da conclusão dos ciclos, para que o participante que nunca
        volta para a retenção também tenha os dados apagados; a retenção concluída o refaz.
        """
        agora = _agora()
        conexao.execute("UPDATE sessao SET concluida_em = ? WHERE id = ?", (_carimbo(agora), sessao_id))
        conexao.execute(
            "UPDATE participante SET retencao_ate = ? WHERE id = (SELECT participante_id FROM sessao WHERE id = ?)",
            (_carimbo(agora + PRAZO_DE_RETENCAO), sessao_id),
        )

    # ------------------------------------------------------------------ exclusão

    def excluir_participante(self, participante_id: str, motivo: MotivoDeExclusao) -> int:
        """Apaga todos os dados do participante e registra a execução. Devolve os eventos apagados."""
        with self.transacao() as conexao:
            if conexao.execute("SELECT 1 FROM participante WHERE id = ?", (participante_id,)).fetchone() is None:
                raise ParticipanteDesconhecido(participante_id)
            conexao.execute("INSERT INTO exclusao_em_curso (participante_id) VALUES (?)", (participante_id,))
            sessoes = "SELECT id FROM sessao WHERE participante_id = ?"
            eventos = conexao.execute(f"DELETE FROM evento WHERE sessao_id IN ({sessoes})", (participante_id,)).rowcount
            conexao.execute(f"DELETE FROM decisao_ciclo WHERE sessao_id IN ({sessoes})", (participante_id,))
            conexao.execute("DELETE FROM sessao WHERE participante_id = ?", (participante_id,))
            conexao.execute("DELETE FROM participante WHERE id = ?", (participante_id,))
            conexao.execute("DELETE FROM exclusao_em_curso WHERE participante_id = ?", (participante_id,))
            conexao.execute(
                "INSERT INTO exclusao (participante_id, motivo, eventos, executada_em) VALUES (?, ?, ?, ?)",
                (participante_id, motivo, eventos, _carimbo(_agora())),
            )
        return eventos

    def expirados(self, agora: datetime | None = None) -> list[str]:
        """Participantes com prazo de retenção vencido."""
        limite = _carimbo(agora or _agora())
        with self.transacao() as conexao:
            linhas = conexao.execute(
                "SELECT id FROM participante WHERE retencao_ate IS NOT NULL AND retencao_ate < ? ORDER BY id",
                (limite,),
            ).fetchall()
        return [str(linha[0]) for linha in linhas]
