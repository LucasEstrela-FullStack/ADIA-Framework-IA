-- Limiares da regra de regulação, editáveis pelo pesquisador e versionados. Cada sessão
-- guarda a versão com que foi criada (sessao.limiares_versao) e é reproduzida com ela:
-- mudar limiar vale para sessões novas, nunca reescreve as antigas.
CREATE TABLE limiares (
    versao                  TEXT PRIMARY KEY,
    independente_fading     TEXT NOT NULL,
    gap_maximo              TEXT NOT NULL,
    vies_maximo_fading      TEXT NOT NULL,
    independente_escalonar  TEXT NOT NULL,
    vies_justificativa      TEXT NOT NULL,
    criado_em               TEXT NOT NULL
) STRICT;

INSERT INTO limiares VALUES ('readme-v1', '0.8', '0.25', '0.2', '0.4', '0.25', '2026-10-30T00:00:00.000+00:00');

CREATE TRIGGER limiares_sem_update BEFORE UPDATE ON limiares
BEGIN
    SELECT RAISE(ABORT, 'limiares é append-only: defina uma versão nova');
END;

CREATE TRIGGER limiares_sem_delete BEFORE DELETE ON limiares
BEGIN
    SELECT RAISE(ABORT, 'limiares é append-only');
END;
