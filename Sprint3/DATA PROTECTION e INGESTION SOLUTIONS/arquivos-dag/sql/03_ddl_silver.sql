DROP TABLE IF EXISTS silver.incidentes_tratados;

CREATE TABLE silver.incidentes_tratados (
    numero               VARCHAR(20)  PRIMARY KEY,
    prioridade           VARCHAR(50)  NOT NULL,
    produto              VARCHAR(500) NOT NULL,
    categoria            VARCHAR(500) NOT NULL,
    subcategoria         VARCHAR(500) NOT NULL,
    grupo_designado      VARCHAR(100) NOT NULL,
    item_configuracao    VARCHAR(500) NOT NULL,
    aberto               TIMESTAMP    NOT NULL,
    resolvido            TIMESTAMP    NOT NULL,
    encerrado            TIMESTAMP    NOT NULL,
    duracao              BIGINT       NOT NULL,
    codigo_fechamento    VARCHAR(500) NOT NULL,
    descricao_resumida   TEXT         NOT NULL,
    solucao              TEXT         NOT NULL,
    aberto_por           VARCHAR(100) NOT NULL,
    incidente_pai        VARCHAR(20),
    status               VARCHAR(50)  NOT NULL,
    entrou_kpi           VARCHAR(10)  NOT NULL,
    kpi_violado_texto    VARCHAR(20)  NOT NULL,
    -- Flags binárias (engenharia de atributos) [4]
    tem_resolucao        SMALLINT     NOT NULL,
    tem_pai              SMALLINT     NOT NULL,
    tem_produto          SMALLINT     NOT NULL,
    tem_categoria        SMALLINT     NOT NULL,
    tem_subcategoria     SMALLINT     NOT NULL,
    tem_item_config      SMALLINT     NOT NULL,
    tem_cf               SMALLINT     NOT NULL,
    kpi_violado          SMALLINT     NOT NULL,
    kpi_nao_aplicavel    SMALLINT     NOT NULL,
    -- Auditoria (obrigatórias do desafio) [2]
    dt_carga             TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    nmn_usuario_carga    VARCHAR(50)  DEFAULT CURRENT_USER
);

CREATE INDEX idx_silver_grupo      ON silver.incidentes_tratados(grupo_designado);
CREATE INDEX idx_silver_prioridade ON silver.incidentes_tratados(prioridade);
CREATE INDEX idx_silver_aberto     ON silver.incidentes_tratados(aberto);
CREATE INDEX idx_silver_status     ON silver.incidentes_tratados(status);