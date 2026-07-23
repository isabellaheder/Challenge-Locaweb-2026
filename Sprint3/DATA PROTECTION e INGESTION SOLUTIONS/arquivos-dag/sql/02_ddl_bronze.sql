DROP TABLE IF EXISTS bronze.incidentes_raw;

CREATE TABLE bronze.incidentes_raw (
    numero               VARCHAR(20),
    prioridade           VARCHAR(50),
    produto              VARCHAR(500),
    categoria            VARCHAR(500),
    subcategoria         VARCHAR(500),
    grupo_designado      VARCHAR(100),
    item_configuracao    VARCHAR(500),
    aberto               TIMESTAMP,
    resolvido            TIMESTAMP,
    encerrado            TIMESTAMP,
    duracao              BIGINT,
    codigo_fechamento    VARCHAR(500),
    descricao_resumida   TEXT,
    solucao              TEXT,
    aberto_por           VARCHAR(100),
    incidente_pai        VARCHAR(20),
    status               VARCHAR(50),
    entrou_kpi           VARCHAR(10),
    kpi_violado          VARCHAR(20),
    dt_carga             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);