"""Tipos de valor compartilhados: ``Nivel``, ``Etapa``, ``Condicao``, ``Decisao``.

Camada mais baixa do contrato de camadas de ``backend/.importlinter`` (design §6.4): nada
aqui pode importar outro módulo de ``adia``. O conteúdo é implementado na tarefa 3.1; este
módulo existe desde a Fase 0 para que o contrato de import e a fronteira de tipo tenham o
que verificar antes de haver código de domínio.
"""
