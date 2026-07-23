"""
Camada GOLD (Curated Zone)
Cria tabelas agregadas para BI/ML/Dashboard/Jornal de Turno.
Versão robusta: cria tabelas se não existirem + logs detalhados.
"""
from sqlalchemy import create_engine, text

PG_CONN = 'postgresql+psycopg2://predictops:predictops123@postgres-dw:5432/predictops_dw'


def aggregate_gold():
    print("Iniciando agregações GOLD...")
    engine = create_engine(PG_CONN)

    # garantir que tabelas existam
    ddl_statements = [
        """
        CREATE SCHEMA IF NOT EXISTS gold;
        """,
        """
        CREATE TABLE IF NOT EXISTS gold.kpi_por_equipe (
            grupo_designado       VARCHAR(100),
            data_referencia       DATE,
            total_incidentes      INT,
            total_violacoes       INT,
            pct_violacao          NUMERIC(8,2),
            duracao_media_seg     NUMERIC(18,2),
            PRIMARY KEY (grupo_designado, data_referencia)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS gold.kpi_por_prioridade (
            prioridade            VARCHAR(50),
            data_referencia       DATE,
            total_incidentes      INT,
            total_violacoes       INT,
            pct_violacao          NUMERIC(8,2),
            PRIMARY KEY (prioridade, data_referencia)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS gold.incidentes_diarios (
            data_referencia       DATE PRIMARY KEY,
            total_abertos         INT,
            total_encerrados      INT,
            total_violacoes_kpi   INT,
            pct_violacao          NUMERIC(8,2)
        );
        """,
    ]

    with engine.begin() as conn:
        for ddl in ddl_statements:
            conn.execute(text(ddl))
        print("Schemas/tabelas verificadas")

    # limpeza
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE gold.kpi_por_equipe"))
        conn.execute(text("TRUNCATE TABLE gold.kpi_por_prioridade"))
        conn.execute(text("TRUNCATE TABLE gold.incidentes_diarios"))
        print("Tabelas Gold truncadas")

    # kpi por equipe (jornal de turno)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO gold.kpi_por_equipe
                (grupo_designado, data_referencia, total_incidentes,
                 total_violacoes, pct_violacao, duracao_media_seg)
                SELECT
                    grupo_designado,
                    CAST(aberto AS DATE) AS data_referencia,
                    COUNT(*)::INT AS total_incidentes,
                    COALESCE(SUM(kpi_violado), 0)::INT AS total_violacoes,
                    ROUND(
                        (100.0 * COALESCE(SUM(kpi_violado), 0)
                         / NULLIF(COUNT(*), 0))::numeric, 2
                    ) AS pct_violacao,
                    ROUND(AVG(duracao)::numeric, 2) AS duracao_media_seg
                FROM silver.incidentes_tratados
                WHERE grupo_designado IS NOT NULL
                  AND aberto IS NOT NULL
                GROUP BY grupo_designado, CAST(aberto AS DATE)
            """))
            print(f"gold.kpi_por_equipe → {result.rowcount} linhas inseridas")
    except Exception as e:
        print(f"Erro em kpi_por_equipe: {e}")
        raise

    # kpi por prioridade (Email Diário)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO gold.kpi_por_prioridade
                (prioridade, data_referencia, total_incidentes,
                 total_violacoes, pct_violacao)
                SELECT
                    prioridade,
                    CAST(aberto AS DATE) AS data_referencia,
                    COUNT(*)::INT AS total_incidentes,
                    COALESCE(SUM(kpi_violado), 0)::INT AS total_violacoes,
                    ROUND(
                        (100.0 * COALESCE(SUM(kpi_violado), 0)
                         / NULLIF(COUNT(*), 0))::numeric, 2
                    ) AS pct_violacao
                FROM silver.incidentes_tratados
                WHERE prioridade IS NOT NULL
                  AND aberto IS NOT NULL
                GROUP BY prioridade, CAST(aberto AS DATE)
            """))
            print(f"gold.kpi_por_prioridade → {result.rowcount} linhas inseridas")
    except Exception as e:
        print(f"Erro em kpi_por_prioridade: {e}")
        raise

    # volume diário (Dashboard)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO gold.incidentes_diarios
                (data_referencia, total_abertos, total_encerrados,
                 total_violacoes_kpi, pct_violacao)
                SELECT
                    CAST(aberto AS DATE) AS data_referencia,
                    COUNT(*)::INT AS total_abertos,
                    COALESCE(SUM(CASE WHEN status IN
                        ('Encerrado','Encerrado Automaticamente') 
                        THEN 1 ELSE 0 END), 0)::INT AS total_encerrados,
                    COALESCE(SUM(kpi_violado), 0)::INT AS total_violacoes_kpi,
                    ROUND(
                        (100.0 * COALESCE(SUM(kpi_violado), 0)
                         / NULLIF(COUNT(*), 0))::numeric, 2
                    ) AS pct_violacao
                FROM silver.incidentes_tratados
                WHERE aberto IS NOT NULL
                GROUP BY CAST(aberto AS DATE)
            """))
            print(f"gold.incidentes_diarios → {result.rowcount} linhas inseridas")
    except Exception as e:
        print(f"Erro em incidentes_diarios: {e}")
        raise

    # conferencia final
    with engine.connect() as conn:
        for tabela in ['kpi_por_equipe', 'kpi_por_prioridade', 'incidentes_diarios']:
            qtd = conn.execute(text(f"SELECT COUNT(*) FROM gold.{tabela}")).scalar()
            print(f"gold.{tabela}: {qtd:,} registros")

    print("GOLD carregada com sucesso!")


if __name__ == '__main__':
    aggregate_gold()