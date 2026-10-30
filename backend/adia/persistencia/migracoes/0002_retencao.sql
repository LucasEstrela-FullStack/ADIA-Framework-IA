-- Teste de retenção de 7 dias (DO-08): quando abriu, com que desvio da janela e quando
-- terminou. O prazo de DO-14 passa a contar da conclusão da retenção.
ALTER TABLE sessao ADD COLUMN retencao_iniciada_em TEXT;
-- Horas além das 216 h da janela; nulo dentro dela (DO-08: fora de protocolo, com marca).
ALTER TABLE sessao ADD COLUMN retencao_desvio_horas TEXT;
ALTER TABLE sessao ADD COLUMN retencao_concluida_em TEXT;
