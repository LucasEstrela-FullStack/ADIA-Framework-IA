"""Erros do banco de itens: as nove falhas de carga e as três falhas de seleção.

Catálogo de §3.1 e §7.2 do design. O módulo guarda **duas** famílias, com raízes
deliberadamente **separadas**, e a separação é a informação mais importante daqui:

- ``ErroDeCarga`` — falha de **conteúdo**, descoberta ao ler ``data/itens/*.adia.toml``.
  Aborta a carga inteira, e com ela a subida da API: banco que não carrega não é servido
  (§7.2). Todo erro desta família nomeia arquivo, linha e campo (R3.2);
- ``ErroDeSelecao`` — falha de **tempo de execução**, descoberta ao atender um pedido sobre
  um banco que já carregou sem erro. Não há arquivo nem linha a reportar, e inventá-los
  seria a precisão fingida que esta família recusa. Recusa o **pedido**, não o banco, e vira
  resposta ``409`` com código próprio (§7.2).

Nenhuma das duas deriva da outra, e é isso que impede o defeito que a hierarquia única
produziria: um ``except ErroDeCarga`` ou um ``isinstance`` no caminho de subida passaria a
capturar a recusa de um pedido e abortaria o serviço por um item pedido na etapa errada —
ou, na direção oposta, um arquivo malformado apareceria ao estudante como ``409`` em vez de
impedir a execução. As duas famílias compartilham só a forma: erro é **valor**, e a
mensagem não cita conteúdo.

Três decisões de forma, e a razão de cada uma:

**1. Erro é valor, não exceção.** ``carregar`` devolve ``CargaConcluida | ErroDeCarga``, no
mesmo padrão de ``BancoDeItens.obter -> Item | ErroDeEtapaNaoPermitida`` (§3.1). Exceção
pode ser engolida por um ``except`` largo no caminho de subida da API; valor de retorno
tipado não pode ser ignorado sem que o ``mypy --strict`` recuse o uso. Como a carga é a
pré-condição de servir (§7.2), a diferença importa.

Vale para as duas famílias, e com uma consequência que a de seleção torna visível: o
``ValueError`` continua reservado ao pedido que **não descreve nada** — conjunto de itens
praticados vazio, identificador repetido na mesma solicitação, etapa com IA pedida a
``elegiveis_sem_ia``. Isso é defeito de quem chama, não indisponibilidade do banco, e
devolvê-lo como valor de erro faria a interface anunciar "conjunto indisponível" para um
banco que tem todos os itens.

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
from enum import StrEnum, unique
from pathlib import Path
from typing import Final

from adia.nucleo.itens.modelo import TipoDeRelacao
from adia.tipos import Etapa, Nivel

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


# --------------------------------------------------------------------------- #
# Raiz dos erros de seleção
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ErroDeSelecao(ABC):
    """Raiz dos erros de tempo de execução do ``Banco_de_Itens`` (§3.1, §7.2).

    **Não** deriva de ``ErroDeCarga``, e a razão não é de gosto. ``ErroDeCarga`` exige
    ``arquivo``, ``linha`` e ``campo`` porque a falha dele *está* num arquivo; aqui o banco
    já carregou sem erro e nenhum arquivo está errado — o que falhou foi o **pedido**. Herdar
    forçaria preencher os três campos com um caminho inventado, que é a precisão fingida que
    o cabeçalho deste módulo recusa, e faria a recusa de um pedido ser capturável como falha
    de carga no caminho de subida da API.

    O que a raiz garante é o par que a API precisa: ``codigo``, que §7.2 fixa por gatilho, e
    ``mensagem``, que é o diagnóstico legível. ``codigo`` é atributo de classe porque é
    contrato de interface — a tabela de §7.2 mapeia gatilho em código HTTP, e manter o código
    ao lado do erro impede que o mapeamento seja reinventado na camada da API.

    Como em ``ErroDeCarga``, nenhuma mensagem cita gabarito, enunciado, variação, termo
    essencial ou texto de dica: a recusa de um pedido chega ao log e, em etapa sem IA, pode
    chegar à tela do estudante.
    """

    @property
    @abstractmethod
    def codigo(self) -> str:
        """Código de interface declarado em §7.2, estável para o cliente da API."""

    @abstractmethod
    def detalhe(self) -> str:
        """Explicação da recusa, sem citar conteúdo de campo sigiloso."""

    @property
    def mensagem(self) -> str:
        """Mensagem completa: código de interface e o que está indisponível."""
        return f"{self.codigo}: {self.detalhe()}"

    def __str__(self) -> str:
        """Texto da mensagem, para que interpolar o erro já produza o diagnóstico."""
        return self.mensagem


# --------------------------------------------------------------------------- #
# Item pedido para etapa que ele não admite, e item que não existe
# --------------------------------------------------------------------------- #

CODIGO_ITEM_FORA_DA_ETAPA: Final = "ITEM_FORA_DA_ETAPA"
CODIGO_ITEM_DESCONHECIDO: Final = "ITEM_DESCONHECIDO"
CODIGO_CONJUNTO_INDISPONIVEL: Final = "CONJUNTO_INDISPONIVEL"
"""Códigos de interface de §7.2. Os dois primeiros respondem ``409`` em ``obter``; o
terceiro responde ``409`` em ``conjunto_do_desafio``.

``ITEM_DESCONHECIDO`` **não** está na tabela de §7.2, e é acréscimo declarado: ver
``ErroDeItemDesconhecido``.
"""


@dataclass(frozen=True)
class ErroDeEtapaNaoPermitida(ErroDeSelecao):
    """Item pedido para etapa ausente de suas ``etapas_permitidas`` (R2.5).

    §7.2 é explícito sobre as duas metades da consequência: a etapa **não** inicia e nenhum
    substituto é escolhido em tempo de execução. A segunda metade é a que exige nome próprio
    para este erro. Um banco que trocasse o item fora da etapa por outro "parecido" produziria
    uma etapa que roda com itens que o protocolo não prescreveu, e a TAI do escopo passaria a
    descrever um conjunto de itens diferente do registrado — sem nada na tela parecer errado.

    ``etapas_permitidas`` vem na recusa porque é o que diz onde o item **pode** ser
    apresentado, e é a informação que falta para corrigir o pedido ou o arquivo. Nenhum dos
    três campos é campo de conteúdo.
    """

    item_id: str
    etapa: Etapa
    etapas_permitidas: frozenset[Etapa]

    @property
    def codigo(self) -> str:
        """``ITEM_FORA_DA_ETAPA`` (§7.2)."""
        return CODIGO_ITEM_FORA_DA_ETAPA

    def detalhe(self) -> str:
        """Diz o item, a etapa pedida e as etapas que ele admite (R2.5)."""
        admitidas = ", ".join(sorted(etapa.value for etapa in self.etapas_permitidas))
        return (
            f"o item {self.item_id!r} não admite a etapa {self.etapa.value!r}; "
            f"etapas permitidas: {admitidas} (R2.5)"
        )


@dataclass(frozen=True)
class ErroDeItemDesconhecido(ErroDeSelecao):
    """Identificador pedido que não corresponde a nenhum item do banco carregado.

    **Acréscimo ao contrato de §3.1**, que declara ``obter -> Item | ErroDeEtapaNaoPermitida``
    e não cobre o identificador inexistente. As três saídas possíveis foram consideradas, e as
    duas descartadas o foram por motivo concreto:

    - *tratar como etapa não permitida* mandaria quem depura olhar as ``etapas_permitidas`` de
      um item que não existe, e a API responderia ``ITEM_FORA_DA_ETAPA`` para um identificador
      obsoleto. É o erro de diagnóstico mais caro dos três;
    - *levantar exceção* contraria o padrão do módulo e tem alvo real: §4.2 registra que
      ``apresentacao_item.item_id`` **não** é chave estrangeira, de modo que um evento antigo
      pode citar item que saiu do banco. Essa referência precisa ser tratável, não fatal.

    Sobra o terceiro tipo no retorno, que é o que o ``mypy --strict`` obriga a distinguir.
    """

    item_id: str
    etapa: Etapa | None = None

    @property
    def codigo(self) -> str:
        """``ITEM_DESCONHECIDO``, acréscimo declarado à tabela de §7.2."""
        return CODIGO_ITEM_DESCONHECIDO

    def detalhe(self) -> str:
        """Diz o identificador pedido, e a etapa quando o pedido a trazia."""
        base = f"o identificador {self.item_id!r} não corresponde a nenhum item do banco carregado"
        if self.etapa is None:
            return base
        return f"{base}; etapa pedida: {self.etapa.value!r}"


# --------------------------------------------------------------------------- #
# Conjunto do desafio independente indisponível
# --------------------------------------------------------------------------- #


@unique
class LacunaDoConjunto(StrEnum):
    """Causa pela qual uma associação exigida pelo desafio independente não está disponível.

    Existe porque "conjunto indisponível" não diz o que consertar, e as cinco causas pedem
    conserto em lugares diferentes: arquivo de item, ``etapas_permitidas``, composição do
    ciclo, histórico do participante e tamanho do banco. As três primeiras são defeito de
    conteúdo que o protocolo pode corrigir; as duas últimas são esgotamento legítimo, que
    R2.7 produz por construção num banco pequeno.

    - ``SEM_CANDIDATO_QUALIFICADO`` — nenhuma relação declarada cumpre o critério de R2.2.
      Num banco carregado pelo ``carregador`` isto só alcança item **não** praticado, porque
      R2.6 já recusaria o praticado na carga;
    - ``FORA_DA_ETAPA`` — os candidatos qualificam, e nenhum admite o desafio independente nas
      suas ``etapas_permitidas`` (R2.4, R2.5);
    - ``PRATICADO_NO_CICLO`` — o único candidato restante é item praticado **neste** ciclo.
      Apresentá-lo faria o desafio medir, sem assistência, um item que acabou de ser resolvido
      com assistência, o que é precisamente o que o par isomorfo existe para evitar;
    - ``JA_APRESENTADO`` — os candidatos elegíveis foram todos consumidos por apresentação
      anterior em etapa sem IA (R2.7);
    - ``DISPUTADO`` — há candidato elegível para cada item praticado, mas não há atribuição que
      dê um equivalente **distinto** a cada um. Ver ``BancoDeItens.conjunto_do_desafio``.

    **Precedência quando mais de uma causa coexiste**, do mais informativo para o menos:
    ``JA_APRESENTADO``, ``PRATICADO_NO_CICLO``, ``FORA_DA_ETAPA``, ``DISPUTADO``,
    ``SEM_CANDIDATO_QUALIFICADO``. A ordem não é arbitrária: "o participante já viu" descreve a
    execução em curso e não se conserta no arquivo, e é a causa que o operador precisa
    distinguir de um defeito de conteúdo; ``DISPUTADO`` vem antes de
    ``SEM_CANDIDATO_QUALIFICADO`` porque na disputa havia candidato qualificado, e dizer o
    contrário seria falso.
    """

    SEM_CANDIDATO_QUALIFICADO = "sem_candidato_qualificado"
    FORA_DA_ETAPA = "fora_da_etapa"
    PRATICADO_NO_CICLO = "praticado_no_ciclo"
    JA_APRESENTADO = "ja_apresentado"
    DISPUTADO = "disputado"


EXPLICACAO_DA_LACUNA: Final = {
    LacunaDoConjunto.SEM_CANDIDATO_QUALIFICADO: "nenhuma relação declarada cumpre o critério de R2.2",
    LacunaDoConjunto.FORA_DA_ETAPA: "nenhum candidato admite a etapa do desafio independente",
    LacunaDoConjunto.PRATICADO_NO_CICLO: "o único candidato restante é item praticado neste ciclo",
    LacunaDoConjunto.JA_APRESENTADO: "todo candidato elegível já foi apresentado em etapa sem IA (R2.7)",
    LacunaDoConjunto.DISPUTADO: (
        "os candidatos elegíveis são disputados e não há atribuição que dê um equivalente "
        "distinto a cada item praticado"
    ),
}
"""Texto de cada causa, para a mensagem. Fica ao lado da enumeração para que acrescentar um
membro sem o texto correspondente seja visível na revisão."""


@dataclass(frozen=True)
class ErroDeConjuntoIncompleto(ErroDeSelecao):
    """O desafio independente não pode ser montado inteiro, e por isso não é montado (R2.10).

    É o erro que a Propriedade 33 existe para exigir. O conjunto parcial é a falha que ela
    impede: ele produziria desafio independente de tamanho diferente do praticado, e o *gap*
    entre desempenho assistido e independente — que é a entrada da regra de regulação —
    ficaria incomparável. Logo, ou o conjunto inteiro, ou **este valor e nenhum item**.

    Os campos são o que R2.10 pede, "o item praticado e a associação indisponível", mais o que
    torna a recusa acionável:

    - ``associacao`` é ``"equivalente"`` ou ``"transferencia"``, isto é, qual das duas faltou;
    - ``item_praticado`` é o item cujo equivalente faltou. É ``None`` **só** na lacuna de
      transferência, e aí a identificação de R2.10 fica com ``praticados`` e ``habilidade``:
      a exigência de transferência é da solicitação e da habilidade alvo, não de um item
      praticado em particular, e eleger um dos praticados para nomear seria apontar um
      culpado arbitrário. Ver a divergência anotada em ``BancoDeItens.conjunto_do_desafio``;
    - ``lacuna`` diz **por que** não há candidato, que é o que separa defeito de conteúdo de
      esgotamento legítimo do banco;
    - as quatro contagens mostram onde os candidatos foram perdidos, sem citar identificador de
      item nenhum além dos que o pedido já trazia.
    """

    praticados: tuple[str, ...]
    habilidade: str
    associacao: TipoDeRelacao
    lacuna: LacunaDoConjunto
    item_praticado: str | None
    candidatos_qualificados: int
    excluidos_por_etapa: int
    excluidos_por_pratica: int
    excluidos_por_apresentacao: int

    @property
    def codigo(self) -> str:
        """``CONJUNTO_INDISPONIVEL`` (§7.2)."""
        return CODIGO_CONJUNTO_INDISPONIVEL

    def detalhe(self) -> str:
        """Diz a associação que faltou, para qual item praticado, e por quê."""
        if self.item_praticado is None:
            alvo = (
                f"a habilidade {self.habilidade!r} não dispõe de item de transferência elegível "
                f"para o desafio dos praticados {list(self.praticados)}"
            )
        else:
            alvo = (
                f"o item praticado {self.item_praticado!r} não dispõe de item {self.associacao!r} "
                f"elegível na habilidade {self.habilidade!r}"
            )
        return (
            f"{alvo}: {EXPLICACAO_DA_LACUNA[self.lacuna]}; "
            f"{self.candidatos_qualificados} candidato(s) qualificado(s), "
            f"{self.excluidos_por_etapa} fora da etapa, "
            f"{self.excluidos_por_pratica} praticado(s) neste ciclo, "
            f"{self.excluidos_por_apresentacao} já apresentado(s). "
            "Nenhum item é devolvido: o conjunto do desafio é tudo ou nada (R2.10)"
        )
