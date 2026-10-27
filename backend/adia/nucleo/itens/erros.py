"""Erros de carga do banco de itens, todos identificando arquivo, linha e campo (R3.2).

Catálogo de §3.1 e §7.2 do design, com as nove classes de falha que abortam a carga. Três
decisões de forma, e a razão de cada uma:

**1. Erro é valor, não exceção.** ``carregar`` devolve ``CargaConcluida | ErroDeCarga``, no
mesmo padrão de ``BancoDeItens.obter -> Item | ErroDeEtapaNaoPermitida`` (§3.1). Exceção
pode ser engolida por um ``except`` largo no caminho de subida da API; valor de retorno
tipado não pode ser ignorado sem que o ``mypy --strict`` recuse o uso. Como a carga é a
pré-condição de servir (§7.2), a diferença importa.

**2. A localização é obrigatória, e a linha pode ser honestamente desconhecida.** Todo erro
carrega ``arquivo``, ``linha`` e ``campo``. ``linha`` é ``int | None`` porque há um caso em
que o carregador não tem linha a oferecer sem inventá-la: a falha que não está *em* um
campo, e sim na ausência de um arquivo inteiro. Onde o campo existe no texto, a linha é a
dele; onde o campo está ausente, a linha é a do cabeçalho ``[[item]]`` que deveria contê-lo
— aproximação declarada, e não precisão fingida.

**3. Mensagem de erro não cita conteúdo.** Nenhuma mensagem interpola ``gabarito``,
``variacoes_gabarito``, ``termos_essenciais``, ``enunciado`` ou texto de dica (§6 da
gramática em ``docs/gramatica-itens.md``). A razão é concreta: a mensagem vai para o
terminal de quem roda ``adia itens validar``, para o log de subida da API e, em último caso,
para uma captura de tela em sala. Gabarito em mensagem de erro é vazamento por outro
caminho — o mesmo que a ``Guarda_de_Vazamento`` fecha no texto da dica. A regra é mecânica,
não disciplinar: ``valor_citavel`` é o único jeito de pôr um valor lido na mensagem, e ele
omite o valor nos campos de conteúdo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from adia.tipos import Nivel

# --------------------------------------------------------------------------- #
# Citação de valores em mensagem
# --------------------------------------------------------------------------- #

CAMPOS_DE_CONTEUDO: Final = frozenset(
    {"enunciado", "gabarito", "variacoes_gabarito", "termos_essenciais", "dicas"}
)
"""Campos cujo valor **nunca** aparece em mensagem de erro (§6 da gramática, R7.6).

``dicas`` entra porque uma dica de L4 é um exemplo resolvido análogo, e o conjunto de
verificação da guarda trata exatamente disso: texto que revela o caminho até a resposta.
"""

VALOR_OMITIDO: Final = "<omitido: campo de conteúdo>"
"""Marca que substitui o valor na mensagem. Dizer que foi omitido é parte da informação."""

CRITERIO_DE_ASSOCIACAO: Final = {
    "equivalente": (
        "o equivalente exige mesma habilidade alvo, mesma dificuldade, identificador e "
        "enunciado distintos do item praticado (R2.2)"
    ),
    "transferencia": (
        "o item de transferência exige a mesma habilidade alvo e `transferencia = true` "
        "declarado nele (R2.2)"
    ),
}
"""O que cada associação precisa cumprir para contar como pareamento válido (R2.2).

Fica aqui, e não no carregador, porque é texto de mensagem: a razão de uma relação declarada
não qualificar é a informação mais útil que o erro pode dar a quem escreveu o arquivo.
"""


def e_campo_de_conteudo(campo: str) -> bool:
    """Se o campo guarda conteúdo que não pode aparecer em mensagem.

    A comparação é pelo primeiro segmento, de modo que ``dicas.L3`` e ``dicas`` recebam o
    mesmo tratamento: o caminho até o valor muda, o sigilo não.
    """
    return campo.split(".", 1)[0] in CAMPOS_DE_CONTEUDO


def valor_citavel(campo: str, valor: object) -> str:
    """Representação do valor lido para uso em mensagem, ou a marca de omissão.

    Único caminho autorizado para pôr em mensagem um valor vindo do arquivo. Fora dos campos
    de conteúdo, a citação é curta e truncada: mensagem de erro é diagnóstico, não despejo de
    arquivo.
    """
    if e_campo_de_conteudo(campo):
        return VALOR_OMITIDO
    texto = repr(valor)
    return texto if len(texto) <= 60 else texto[:57] + "..."


def nome_do_tipo(valor: object) -> str:
    """Nome do tipo lido, para a mensagem dizer o que veio sem dizer qual era o valor."""
    return type(valor).__name__


# --------------------------------------------------------------------------- #
# Raiz do catálogo
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ErroDeCarga(ABC):
    """Raiz dos erros de carga. Garante os três elementos que R3.2 exige na mensagem.

    Abstrata de propósito: não existe "erro de carga genérico". Cada falha das nove classes
    de §3.1 tem nome próprio, porque o nome é o que permite a um teste dirigido afirmar
    **qual** rejeição ocorreu, em vez de afirmar que alguma coisa deu errado.
    """

    arquivo: Path
    linha: int | None
    campo: str

    @abstractmethod
    def detalhe(self) -> str:
        """Explicação da falha, sem citar conteúdo de campo sigiloso."""

    @property
    def local(self) -> str:
        """``arquivo:linha`` quando há linha; só o arquivo quando não há."""
        if self.linha is None:
            return str(self.arquivo)
        return f"{self.arquivo}:{self.linha}"

    @property
    def mensagem(self) -> str:
        """Mensagem completa: arquivo, linha, campo e o que está errado (R3.2)."""
        return f"{self.local}: campo `{self.campo}`: {self.detalhe()}"

    def __str__(self) -> str:
        """Texto da mensagem, para que interpolar o erro já produza o diagnóstico."""
        return self.mensagem


# --------------------------------------------------------------------------- #
# As nove classes de falha
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ErroDeGramatica(ErroDeCarga):
    """O arquivo não é interpretável conforme a gramática documentada (R3.2).

    Cobre as três formas da mesma falha, que do ponto de vista da medida são indistinguíveis
    — conteúdo que o carregador não entende não tem como ser medido:

    - sintaxe de TOML inválida, com linha e coluna vindas do interpretador;
    - estrutura inesperada: chave desconhecida, tabela onde se esperava lista, campo ausente;
    - valor do tipo errado: texto onde se esperava inteiro, número de ponto flutuante onde a
      gramática exige cadeia decimal.

    ``motivo`` descreve a **forma** esperada, não o valor encontrado.
    """

    motivo: str

    @classmethod
    def de(cls, arquivo: Path, linha: int | None, campo: str, motivo: str) -> ErroDeGramatica:
        """Constrói o erro com a localização e o motivo já compostos."""
        return cls(arquivo=arquivo, linha=linha, campo=campo, motivo=motivo)

    def detalhe(self) -> str:
        """O motivo, tal como composto na verificação que rejeitou o arquivo."""
        return self.motivo


@dataclass(frozen=True)
class ErroDeIdentificadorDuplicado(ErroDeCarga):
    """Dois itens compartilham o mesmo ``id`` (R3.6).

    Fechada porque o ``id`` é a única referência de item que existe fora dos arquivos:
    ``apresentacao_item.item_id`` não é chave estrangeira (§4.2), e com dois itens sob o
    mesmo nome todo escopo de cálculo fica ambíguo — a TAI do pós-teste passaria a somar
    respostas a enunciados diferentes.

    Nomeia os **dois** arquivos em que o identificador aparece (§7.2), inclusive quando são
    o mesmo arquivo duas vezes.
    """

    identificador: str
    arquivo_anterior: Path
    linha_anterior: int | None

    @classmethod
    def de(
        cls,
        arquivo: Path,
        linha: int | None,
        identificador: str,
        arquivo_anterior: Path,
        linha_anterior: int | None,
    ) -> ErroDeIdentificadorDuplicado:
        """Constrói o erro a partir da segunda ocorrência, guardando a primeira."""
        return cls(
            arquivo=arquivo,
            linha=linha,
            campo="id",
            identificador=identificador,
            arquivo_anterior=arquivo_anterior,
            linha_anterior=linha_anterior,
        )

    @property
    def local_anterior(self) -> str:
        """``arquivo:linha`` da primeira ocorrência do identificador."""
        if self.linha_anterior is None:
            return str(self.arquivo_anterior)
        return f"{self.arquivo_anterior}:{self.linha_anterior}"

    def detalhe(self) -> str:
        """Diz o identificador repetido e onde está a primeira ocorrência."""
        return (
            f"o identificador {self.identificador!r} já foi declarado em {self.local_anterior}; "
            "cada item tem identificador único (R3.6)"
        )


@dataclass(frozen=True)
class ErroDeAssociacaoAusente(ErroDeCarga):
    """Item praticado sem equivalente **ou** sem transferência associada (R2.6).

    Reporta **qual** das duas falta, porque as duas ausências custam coisas diferentes: sem
    equivalente não há desafio independente comparável ao que foi praticado, e sem
    transferência não há TT. A verificação exige mais que a existência da relação — o
    equivalente precisa cumprir R2.2 (mesma habilidade, mesma dificuldade, identificador e
    enunciado distintos), e relação declarada que não qualifica conta como ausência, não como
    pareamento parcial.
    """

    identificador: str
    associacao: str
    candidatos_desqualificados: int

    @classmethod
    def de(
        cls,
        arquivo: Path,
        linha: int | None,
        identificador: str,
        associacao: str,
        candidatos_desqualificados: int = 0,
    ) -> ErroDeAssociacaoAusente:
        """Constrói o erro nomeando a associação que falta."""
        return cls(
            arquivo=arquivo,
            linha=linha,
            campo=f"relacao.{associacao}",
            identificador=identificador,
            associacao=associacao,
            candidatos_desqualificados=candidatos_desqualificados,
        )

    def detalhe(self) -> str:
        """Diz o item, a associação ausente e se havia relação declarada que não qualificou."""
        base = (
            f"o item {self.identificador!r} é apresentado na prática assistida e não tem "
            f"associação {self.associacao!r} válida (R2.6)"
        )
        if self.candidatos_desqualificados:
            criterio = CRITERIO_DE_ASSOCIACAO.get(self.associacao, "")
            return (
                f"{base}; {self.candidatos_desqualificados} relação(ões) declarada(s) não "
                f"qualificam: {criterio}"
            )
        return base


@dataclass(frozen=True)
class ErroDeConflitoDeRelacao(ErroDeCarga):
    """Item de transferência marcado como isomorfo a item praticado da mesma habilidade (R2.9).

    Fechada pela razão mais silenciosa do catálogo: isomorfia transforma transferência em
    repetição e **infla a TT** sem que nada pareça errado na tela. Um protótipo que aceitasse
    isso mediria memória de forma como transferência de habilidade.
    """

    identificador: str
    item_praticado: str
    habilidade_alvo: str

    @classmethod
    def de(
        cls,
        arquivo: Path,
        linha: int | None,
        identificador: str,
        item_praticado: str,
        habilidade_alvo: str,
    ) -> ErroDeConflitoDeRelacao:
        """Constrói o erro nomeando os dois itens em conflito e a habilidade comum."""
        return cls(
            arquivo=arquivo,
            linha=linha,
            campo="relacao.equivalente",
            identificador=identificador,
            item_praticado=item_praticado,
            habilidade_alvo=habilidade_alvo,
        )

    def detalhe(self) -> str:
        """Diz qual item de transferência conflita com qual item praticado."""
        return (
            f"o item de transferência {self.identificador!r} está marcado como isomorfo ao item "
            f"praticado {self.item_praticado!r} da mesma habilidade {self.habilidade_alvo!r}; "
            "transferência e isomorfismo são exclusivos (R2.9)"
        )


@dataclass(frozen=True)
class ErroDePerfilIncompleto(ErroDeCarga):
    """Falta o campo que o tipo de gabarito torna obrigatório (R2.8, R2.11, R7.6).

    Duas das nove classes de falha passam por aqui, e o ``campo`` é o que as distingue:

    - ``"tolerancia"`` em item ``NUMERICO`` — sem ela não existe critério de acerto, e a
      correção de R4.2 não tem o que aplicar;
    - ``"termos_essenciais"`` em item ``TEXTUAL`` — sem eles o detector da guarda não tem
      contra o que comparar, e §7.2 registra a consequência: guarda cega aprovaria vazamento.
    """

    identificador: str
    tipo_gabarito: str

    @classmethod
    def de(
        cls, arquivo: Path, linha: int | None, identificador: str, campo: str, tipo_gabarito: str
    ) -> ErroDePerfilIncompleto:
        """Constrói o erro nomeando o campo exigido pelo tipo de gabarito."""
        return cls(
            arquivo=arquivo,
            linha=linha,
            campo=campo,
            identificador=identificador,
            tipo_gabarito=tipo_gabarito,
        )

    def detalhe(self) -> str:
        """Diz o item, o tipo de gabarito e o campo que ele torna obrigatório."""
        return (
            f"o item {self.identificador!r} tem gabarito {self.tipo_gabarito!r} e não declara "
            f"`{self.campo}`, obrigatório nesse tipo (R2.8, R2.11)"
        )


@dataclass(frozen=True)
class ErroDeEtapasVazias(ErroDeCarga):
    """``etapas_permitidas`` declarado vazio (R2.4).

    Item sem etapa permitida não é item restrito: é item que nenhuma etapa pode apresentar, e
    cuja presença no banco só serve para enganar a contagem de itens disponíveis. R2.4 exige
    conjunto **não vazio**, e a recusa acontece na carga em vez de na seleção.
    """

    identificador: str

    @classmethod
    def de(cls, arquivo: Path, linha: int | None, identificador: str) -> ErroDeEtapasVazias:
        """Constrói o erro para o item sem nenhuma etapa permitida."""
        return cls(arquivo=arquivo, linha=linha, campo="etapas_permitidas", identificador=identificador)

    def detalhe(self) -> str:
        """Diz o item e repete a exigência de conjunto não vazio."""
        return (
            f"o item {self.identificador!r} declara conjunto vazio de etapas permitidas; "
            "R2.4 exige ao menos uma etapa"
        )


@dataclass(frozen=True)
class ErroDeDicaAusente(ErroDeCarga):
    """Falta dica pré-escrita em algum nível de L1 a L4 (R2.1).

    O catálogo pré-escrito é o conteúdo primário da assistência na Fase 3 e a contingência
    de toda falha de geração (D15, R17.7): quando a guarda reprova o texto gerado, é a dica
    do **mesmo nível** que é entregue. Nível faltando no arquivo é, portanto, assistência
    indisponível no momento em que a geração falha — exatamente o pior momento.

    Dica declarada vazia conta como ausente: espaço em branco não é dica.
    """

    identificador: str
    nivel: Nivel

    @classmethod
    def de(cls, arquivo: Path, linha: int | None, identificador: str, nivel: Nivel) -> ErroDeDicaAusente:
        """Constrói o erro nomeando o nível sem dica."""
        return cls(
            arquivo=arquivo,
            linha=linha,
            campo=f"dicas.{nivel.name}",
            identificador=identificador,
            nivel=nivel,
        )

    def detalhe(self) -> str:
        """Diz o item e o nível cuja dica falta, sem citar nenhum texto de dica."""
        return (
            f"o item {self.identificador!r} não declara dica pré-escrita não vazia para "
            f"{self.nivel.name}; R2.1 exige exatamente uma por nível de L1 a L4"
        )


@dataclass(frozen=True)
class ErroDeFaixa(ErroDeCarga):
    """Valor numérico fora da faixa declarada pela gramática (R2.1, R2.8).

    Alcança ``dificuldade`` fora de 1 a 5 (a faixa de DO-01), ``tamanho_max_resposta`` não
    positivo e ``tolerancia`` negativa, que R2.8 exige como valor real **não negativo**. O
    valor encontrado aparece na mensagem porque nenhum dos três é campo de conteúdo.
    """

    identificador: str
    valor: str
    faixa: str

    @classmethod
    def de(
        cls, arquivo: Path, linha: int | None, identificador: str, campo: str, valor: object, faixa: str
    ) -> ErroDeFaixa:
        """Constrói o erro com o valor encontrado e a faixa esperada."""
        return cls(
            arquivo=arquivo,
            linha=linha,
            campo=campo,
            identificador=identificador,
            valor=valor_citavel(campo, valor),
            faixa=faixa,
        )

    def detalhe(self) -> str:
        """Diz o item, o valor encontrado e a faixa que a gramática declara."""
        return f"o item {self.identificador!r} tem `{self.campo}` = {self.valor}, fora da faixa {self.faixa}"
