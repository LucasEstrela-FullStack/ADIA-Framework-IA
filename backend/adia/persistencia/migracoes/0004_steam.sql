-- Projeto STEAM (R13): a submissão do estudante e as avaliações da justificativa por rubrica.
--
-- Append-only como o registro de eventos, com a mesma exceção da exclusão de DO-14. A
-- submissão guarda o resultado de cada parte numérica, e o replay usa esse resultado em vez
-- de recorrigir: a sessão gravada não muda de veredito se o cenário for editado depois.

CREATE TABLE submissao_steam (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sessao_id         TEXT NOT NULL UNIQUE REFERENCES sessao (id),
    cenario_id        TEXT NOT NULL,
    -- Teto vigente na submissão, decidido pela regulação e não pelo conteúdo (gramatica-steam §2).
    teto              INTEGER NOT NULL CHECK (teto BETWEEN 1 AND 4),
    -- JSON [{parte, valor, resultado, tolerancia}], nomes do evento steam_submetido (§4.4).
    partes_numericas  TEXT NOT NULL,
    justificativa     TEXT NOT NULL CHECK (length(justificativa) > 0),
    rubrica_id        TEXT NOT NULL,
    rubrica_versao    INTEGER NOT NULL CHECK (rubrica_versao > 0),
    criado_em         TEXT NOT NULL
) STRICT;

CREATE TABLE avaliacao_rubrica (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    submissao_id         INTEGER NOT NULL REFERENCES submissao_steam (id),
    avaliador_id         TEXT NOT NULL CHECK (avaliador_id GLOB 'PROF-[0-9][0-9]'),
    rubrica_versao       INTEGER NOT NULL CHECK (rubrica_versao > 0),
    -- JSON [{criterio, nivel, pontos}] (§4.3).
    pontuacoes           TEXT NOT NULL,
    criterios_pontuados  INTEGER NOT NULL,
    criterios_total      INTEGER NOT NULL,
    pontos               INTEGER NOT NULL CHECK (pontos >= 0),
    pontos_maximos       INTEGER NOT NULL CHECK (pontos_maximos > 0 AND pontos <= pontos_maximos),
    concluida            INTEGER NOT NULL CHECK (concluida IN (0, 1)),
    criado_em            TEXT NOT NULL,
    UNIQUE (submissao_id, avaliador_id, rubrica_versao),
    -- R13.4: a avaliação só conclui com todos os critérios pontuados.
    CHECK (concluida = 0 OR criterios_pontuados = criterios_total)
) STRICT;

CREATE TRIGGER submissao_steam_sem_update BEFORE UPDATE ON submissao_steam
BEGIN
    SELECT RAISE(ABORT, 'submissao_steam é append-only');
END;

CREATE TRIGGER submissao_steam_sem_delete BEFORE DELETE ON submissao_steam
WHEN NOT EXISTS (
    SELECT 1 FROM exclusao_em_curso e JOIN sessao s ON s.participante_id = e.participante_id
    WHERE s.id = OLD.sessao_id
)
BEGIN
    SELECT RAISE(ABORT, 'submissao_steam é append-only');
END;

CREATE TRIGGER avaliacao_rubrica_sem_update BEFORE UPDATE ON avaliacao_rubrica
BEGIN
    SELECT RAISE(ABORT, 'avaliacao_rubrica é append-only');
END;

CREATE TRIGGER avaliacao_rubrica_sem_delete BEFORE DELETE ON avaliacao_rubrica
WHEN NOT EXISTS (
    SELECT 1 FROM exclusao_em_curso e
    JOIN sessao s ON s.participante_id = e.participante_id
    JOIN submissao_steam m ON m.sessao_id = s.id
    WHERE m.id = OLD.submissao_id
)
BEGIN
    SELECT RAISE(ABORT, 'avaliacao_rubrica é append-only');
END;
