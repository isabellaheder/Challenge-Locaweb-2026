-- ============================================================
-- DDL da camada GOLD (Curated Zone)
-- PredictOps 360 - Sprint 3 | Data Protection & Ingestion
-- 
-- OBSERVAÇÃO: Este script é mantido para fins de documentação 
-- e provisionamento inicial. A criação das tabelas também é 
-- garantida em runtime pelo script gold_aggregate.py 
-- (CREATE TABLE IF NOT EXISTS), conferindo idempotência ao 
-- pipeline.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS gold;

DROP TABLE IF EXISTS gold.kpi_por_equipe;
DROP TABLE IF EXISTS gold.kpi_por_prioridade;
DROP TABLE IF EXISTS gold.incidentes_diarios;

-- KPIs por equipe (alimenta Jornal de Turno) [1]
CREATE TABLE gold.kpi_por_equipe (
    grupo_designado       VARCHAR(100),
    data_referencia       DATE,
    total_incidentes      INT,
    total_violacoes       INT,
    pct_violacao          NUMERIC(8,2),
    duracao_media_seg     NUMERIC(18,2),
    PRIMARY KEY (grupo_designado, data_referencia)
);

-- KPIs por prioridade (alimenta Email Diário) [1]
CREATE TABLE gold.kpi_por_prioridade (
    prioridade            VARCHAR(50),
    data_referencia       DATE,
    total_incidentes      INT,
    total_violacoes       INT,
    pct_violacao          NUMERIC(8,2),
    PRIMARY KEY (prioridade, data_referencia)
);

-- Volume diário (alimenta Dashboard Estratégico) [1]
CREATE TABLE gold.incidentes_diarios (
    data_referencia       DATE PRIMARY KEY,
    total_abertos         INT,
    total_encerrados      INT,
    total_violacoes_kpi   INT,
    pct_violacao          NUMERIC(8,2)
);

-- Comentários documentais
COMMENT ON SCHEMA gold IS 'Curated Zone - dados agregados para BI/ML/Dashboard';
COMMENT ON TABLE gold.kpi_por_equipe IS 'Agregação por equipe e data - alimenta Jornal de Turno';
COMMENT ON TABLE gold.kpi_por_prioridade IS 'Agregação por prioridade e data - alimenta Email Diário';
COMMENT ON TABLE gold.incidentes_diarios IS 'Volume diário consolidado - alimenta Dashboard';