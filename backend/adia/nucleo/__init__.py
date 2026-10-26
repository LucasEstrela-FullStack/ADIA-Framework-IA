"""Núcleo determinístico: itens, correção, regulação, métricas, sessão e eventos.

Lado determinístico da fronteira de D1. O contrato ``nucleo-puro`` proíbe aqui ``adia.ia``,
a rede e o relógio (``time``, ``uuid``, ``secrets``): o relógio é injetado (design §3.0).
"""
