CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

COMMENT ON SCHEMA bronze IS 'Raw Zone - dados brutos extraídos do CSV';
COMMENT ON SCHEMA silver IS 'Staging Zone - dados limpos e validados';
COMMENT ON SCHEMA gold  IS 'Curated Zone - dados agregados para BI/ML';