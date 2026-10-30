-- Sessões e registro de eventos. O registro é append-only: a sessão é reconstruída
-- reaplicando os eventos em ordem de id, então reescrever um evento reescreveria a medida.

CREATE TABLE sessao (
    id         TEXT PRIMARY KEY,
    condicao   TEXT NOT NULL CHECK (condicao IN ('A', 'B', 'C')),
    semente    INTEGER NOT NULL,
    criada_em  TEXT NOT NULL
) STRICT;

CREATE TABLE evento (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sessao_id   TEXT NOT NULL REFERENCES sessao (id),
    tipo        TEXT NOT NULL CHECK (tipo IN ('dica', 'resposta')),
    etapa       TEXT NOT NULL,
    ciclo       INTEGER NOT NULL,
    item_id     TEXT NOT NULL,
    teto        INTEGER NOT NULL CHECK (teto BETWEEN 1 AND 4),
    -- dica
    nivel       INTEGER CHECK (nivel BETWEEN 1 AND 4),
    explicacao  TEXT,
    texto_dica  TEXT,
    origem      TEXT CHECK (origem IN ('ia', 'pre-escrita')),
    motivo      TEXT,
    -- resposta
    resposta    TEXT,
    acerto      INTEGER CHECK (acerto IN (0, 1)),
    confianca   INTEGER CHECK (confianca BETWEEN 0 AND 10),
    criado_em   TEXT NOT NULL,
    CHECK ((tipo = 'dica') = (nivel IS NOT NULL AND texto_dica IS NOT NULL AND origem IS NOT NULL)),
    CHECK ((tipo = 'resposta') = (resposta IS NOT NULL AND confianca IS NOT NULL))
) STRICT;

CREATE INDEX evento_por_sessao ON evento (sessao_id, id);

CREATE TRIGGER evento_sem_update BEFORE UPDATE ON evento
BEGIN
    SELECT RAISE(ABORT, 'evento é append-only');
END;

CREATE TRIGGER evento_sem_delete BEFORE DELETE ON evento
BEGIN
    SELECT RAISE(ABORT, 'evento é append-only');
END;
