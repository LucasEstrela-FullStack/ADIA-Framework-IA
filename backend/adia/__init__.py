"""Pacote do protótipo ADIA-CognitiveLoop.

Deliberadamente vazio de domínio. Os tipos de valor compartilhados — `Nivel`,
`Etapa`, `Condicao`, `Medida` e os demais — ficam em `adia.tipos`, e cada
componente vive no próprio módulo. A fronteira determinística de D1 separa
`adia.nucleo` e `adia.guarda` das camadas com efeito colateral, e um pacote raiz
que reexportasse símbolos daria a essa fronteira um atalho por importação.

O que existe aqui é só o necessário para que `adia.cli` seja importável e para
que o ponto de entrada `adia` declarado em `pyproject.toml` resolva.
"""
