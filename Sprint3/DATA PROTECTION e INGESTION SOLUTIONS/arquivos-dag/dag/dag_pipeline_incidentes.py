"""
DAG: pipeline_incidentes_predictops360
Pipeline completo de ingestão e processamento dos incidentes Locaweb.
"""
from datetime import datetime, timedelta
import sys
import os

# ===== Adicionar pasta scripts ao PYTHONPATH (forma robusta) =====
SCRIPTS_PATH = '/opt/airflow/scripts'
if SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, SCRIPTS_PATH)

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator


def _extract():
    from extract import extract_to_csv
    return extract_to_csv()

def _bronze():
    from bronze_load import load_bronze
    return load_bronze()

def _silver():
    from silver_transform import transform_silver
    return transform_silver()

def _validar():
    from validacao import validar_silver
    return validar_silver()

def _gold():
    from gold_aggregate import aggregate_gold
    return aggregate_gold()


default_args = {
    'owner': 'predictops360',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}

with DAG(
    dag_id='pipeline_incidentes_predictops360',
    default_args=default_args,
    description='Pipeline ETL de incidentes Locaweb - Sprint 3 [PredictOps 360]',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['etl', 'predictops360', 'sprint3', 'locaweb'],
) as dag:

    inicio = EmptyOperator(task_id='inicio')

    t_extract = PythonOperator(
        task_id='1_extracao_excel_para_csv',
        python_callable=_extract,
    )

    t_bronze = PythonOperator(
        task_id='2_carga_bronze_raw_zone',
        python_callable=_bronze,
    )

    t_silver = PythonOperator(
        task_id='3_transformacao_silver_staging',
        python_callable=_silver,
    )

    t_valid = PythonOperator(
        task_id='4_validacao_qualidade_dados',
        python_callable=_validar,
    )

    t_gold = PythonOperator(
        task_id='5_agregacao_gold_curated',
        python_callable=_gold,
    )

    fim = EmptyOperator(task_id='fim')

    inicio >> t_extract >> t_bronze >> t_silver >> t_valid >> t_gold >> fim