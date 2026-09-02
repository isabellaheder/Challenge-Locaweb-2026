import subprocess

ETAPAS = [
    "01_bronze_para_silver.py",
    "models/incidente_d1_d7.py",
    "models/sla_risco.py",
    "models/previsao_turno.py",
    "models/previsao_duracao.py",
    "models/cluster.py",
    "publish_silver_bigquery.py",
    "publish_bigquery.py"]

for etapa in ETAPAS:
    print(f"\n{'='*60}")
    print(f"Executando: {etapa}")
    print(f"{'='*60}")

    subprocess.run(
        ["python", etapa],
        check=True)

print("\nPipeline concluído com sucesso.")
