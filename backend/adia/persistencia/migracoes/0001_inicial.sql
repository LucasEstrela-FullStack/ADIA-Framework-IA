-- Participantes, sessões, registro de eventos, decisões por ciclo e auditoria de exclusão.
--
-- O registro de eventos é append-only: a sessão é reconstruída reaplicando os eventos em
-- ordem de id, então reescrever um evento reescreveria a medida. A única exceção é a
-- exclusão de dados de um participante (DO-14, LGPD), que só passa pelos gatilhos quando
-- o participante está em `exclusao_em_curso`, tabela preenchida e esvaziada na mesma
-- transação pelo comando `adia excluir-dados`.

-- Pseudônimo apenas: o vínculo com a identidade vive fora do banco (DO-19).
CREATE TABLE participante (
    id            TEXT PRIMARY KEY CHECK (id GLOB 'P-[0-9][0-9][0-9][0-9]'),
    coorte        TEXT NOT NULL CHECK (length(coorte) > 0),
    criado_em     TEXT NOT NULL,
    -- 180 dias após a conclusão (DO-14); nulo enquanto a coleta não terminou.
    retencao_ate  TEXT
) STRICT;

CREATE TABLE sessao (
    id                  TEXT PRIMARY KEY,
    participante_id     TEXT NOT NULL UNIQUE REFERENCES participante (id),
    condicao            TEXT NOT NULL CHECK (condicao IN ('A', 'B', 'C')),
    -- DO-07: semente do sorteio entre as condições de menor contagem na coorte.
    semente_atribuicao  INTEGER NOT NULL,
    semente_banco       INTEGER NOT NULL,
    -- Proveniência (R26): o que é preciso para reproduzir a sessão.
    hash_banco_itens    TEXT NOT NULL,
    commit_codigo       TEXT,
    modelo              TEXT NOT NULL,
    limiares_versao     TEXT NOT NULL,
    criada_em           TEXT NOT NULL,
    concluida_em        TEXT
) STRICT;

CREATE TABLE evento (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sessao_id     TEXT NOT NULL REFERENCES sessao (id),
    tipo          TEXT NOT NULL CHECK (tipo IN ('dica', 'resposta')),
    etapa         TEXT NOT NULL,
    ciclo         INTEGER NOT NULL,
    item_id       TEXT NOT NULL,
    teto          INTEGER NOT NULL CHECK (teto BETWEEN 1 AND 4),
    -- dica
    nivel         INTEGER CHECK (nivel BETWEEN 1 AND 4),
    explicacao    TEXT,
    texto_dica    TEXT,
    origem        TEXT CHECK (origem IN ('ia', 'pre-escrita')),
    motivo        TEXT,
    -- resposta
    resposta      TEXT,
    justificativa TEXT,
    acerto        INTEGER CHECK (acerto IN (0, 1)),
    confianca     INTEGER CHECK (confianca BETWEEN 0 AND 10),
    criado_em     TEXT NOT NULL,
    CHECK ((tipo = 'dica') = (nivel IS NOT NULL AND texto_dica IS NOT NULL AND origem IS NOT NULL)),
    CHECK ((tipo = 'resposta') = (resposta IS NOT NULL AND confianca IS NOT NULL))
) STRICT;

CREATE INDEX evento_por_sessao ON evento (sessao_id, id);

-- Decisão de cada ciclo como foi tomada, inclusive a sombra das condições A e C (R14.2,
-- R14.4). O replay recalcula e compara com esta linha: divergência é erro, nunca correção.
CREATE TABLE decisao_ciclo (
    sessao_id             TEXT NOT NULL REFERENCES sessao (id),
    ciclo                 INTEGER NOT NULL,
    teto                  INTEGER NOT NULL CHECK (teto BETWEEN 1 AND 4),
    acerto_assistido      TEXT,
    acerto_independente   TEXT,
    confianca             TEXT,
    gap                   TEXT,
    vies                  TEXT,
    evidencia_incompleta  TEXT,
    decisao               TEXT NOT NULL CHECK (decisao IN ('fading', 'onloading', 'escalonar', 'manter')),
    teto_indicado         INTEGER NOT NULL CHECK (teto_indicado BETWEEN 1 AND 4),
    teto_aplicado         INTEGER NOT NULL CHECK (teto_aplicado BETWEEN 1 AND 4),
    aplicada              INTEGER NOT NULL CHECK (aplicada IN (0, 1)),
    limiares_versao       TEXT NOT NULL,
    criado_em             TEXT NOT NULL,
    PRIMARY KEY (sessao_id, ciclo)
) STRICT;

-- Auditoria das exclusões: sem dado do participante além do pseudônimo.
CREATE TABLE exclusao (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    participante_id  TEXT NOT NULL,
    motivo           TEXT NOT NULL CHECK (motivo IN ('pedido', 'prazo_expirado')),
    eventos          INTEGER NOT NULL,
    executada_em     TEXT NOT NULL
) STRICT;

CREATE TABLE exclusao_em_curso (
    participante_id  TEXT PRIMARY KEY
) STRICT;

CREATE TRIGGER evento_sem_update BEFORE UPDATE ON evento
BEGIN
    SELECT RAISE(ABORT, 'evento é append-only');
END;

CREATE TRIGGER evento_sem_delete BEFORE DELETE ON evento
WHEN NOT EXISTS (
    SELECT 1 FROM exclusao_em_curso e JOIN sessao s ON s.participante_id = e.participante_id
    WHERE s.id = OLD.sessao_id
)
BEGIN
    SELECT RAISE(ABORT, 'evento é append-only');
END;

CREATE TRIGGER decisao_sem_update BEFORE UPDATE ON decisao_ciclo
BEGIN
    SELECT RAISE(ABORT, 'decisao_ciclo é append-only');
END;

CREATE TRIGGER decisao_sem_delete BEFORE DELETE ON decisao_ciclo
WHEN NOT EXISTS (
    SELECT 1 FROM exclusao_em_curso e JOIN sessao s ON s.participante_id = e.participante_id
    WHERE s.id = OLD.sessao_id
)
BEGIN
    SELECT RAISE(ABORT, 'decisao_ciclo é append-only');
END;

CREATE TRIGGER exclusao_sem_update BEFORE UPDATE ON exclusao
BEGIN
    SELECT RAISE(ABORT, 'exclusao é append-only');
END;

CREATE TRIGGER exclusao_sem_delete BEFORE DELETE ON exclusao
BEGIN
    SELECT RAISE(ABORT, 'exclusao é append-only');
END;
