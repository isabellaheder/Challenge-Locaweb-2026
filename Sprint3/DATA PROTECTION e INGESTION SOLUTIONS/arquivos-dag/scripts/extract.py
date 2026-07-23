"""
Camada de EXTRAÇÃO
Lê o arquivo Excel original e converte para CSV padronizado.
"""
import pandas as pd
from pathlib import Path
from datetime import datetime


def extract_to_csv():
    src = Path('/opt/airflow/data/raw/LW-DATASET.xlsx')
    dst = Path('/opt/airflow/data/raw/LW-DATASET.csv')

    if not src.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {src}")

    print(f"Lendo {src}...")
    df = pd.read_excel(src)

    print(f"Shape original: {df.shape}")
    print(f"Colunas: {list(df.columns)}")

    df.to_csv(dst, index=False, sep=';', encoding='utf-8-sig')

    print(f"Extração concluída: {len(df):,} registros salvos em {dst}")
    print(f"Timestamp: {datetime.now()}")
    return str(dst)


if __name__ == '__main__':
    extract_to_csv()