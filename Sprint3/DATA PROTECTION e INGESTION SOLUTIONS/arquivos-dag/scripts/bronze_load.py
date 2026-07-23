"""
Camada BRONZE (Raw Zone)
Carrega o CSV bruto no PostgreSQL sem nenhuma transformação.
"""
import pandas as pd
from sqlalchemy import create_engine, text

PG_CONN = 'postgresql+psycopg2://predictops:predictops123@postgres-dw:5432/predictops_dw'


def load_bronze():
    print("🥉 Iniciando carga BRONZE...")

    df = pd.read_csv(
        '/opt/airflow/data/raw/LW-DATASET.csv',
        sep=';',
        encoding='utf-8-sig'
    )

    print(f"Registros lidos do CSV: {len(df):,}")

    # Renomear colunas (snake_case, sem acentos)
    df.columns = [
        'numero', 'prioridade', 'produto', 'categoria', 'subcategoria',
        'grupo_designado', 'item_configuracao', 'aberto', 'resolvido',
        'encerrado', 'duracao', 'codigo_fechamento', 'descricao_resumida',
        'solucao', 'aberto_por', 'incidente_pai', 'status', 'entrou_kpi',
        'kpi_violado'
    ]

    engine = create_engine(PG_CONN)

    # Truncar antes (idempotência)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE bronze.incidentes_raw"))
        print("bronze.incidentes_raw truncada")

    # Inserir
    df.to_sql(
        'incidentes_raw',
        engine,
        schema='bronze',
        if_exists='append',
        index=False,
        chunksize=5000,
        method='multi'
    )

    # Conferência
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM bronze.incidentes_raw")).scalar()

    print(f"BRONZE carregada: {total:,} registros em bronze.incidentes_raw")
    return total


if __name__ == '__main__':
    load_bronze()