"""Guarda de vazamento: perfil, normalização, aritmética, detectores e veredito.

Determinística por D3, e irmã independente de ``adia.ia`` no contrato de camadas. O
contrato ``guarda-pura`` proíbe aqui ``adia.ia`` e a rede, mas **permite** ``time``: o
orçamento de 2 s é medido com ``time.monotonic()`` (design §3.11).
"""
