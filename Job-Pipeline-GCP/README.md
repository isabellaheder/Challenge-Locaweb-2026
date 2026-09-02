# Visão Geral

O PredictOps é uma plataforma preditiva para operações de TI construída na Google Cloud Platform utilizando arquitetura Bronze, Silver e Gold.

A solução processa dados de incidentes, treina modelos de Machine Learning, gera previsões e publica os resultados no BigQuery para consumo pelo Power BI.

## Pipeline
Cloud Storage (Bronze) -> Cloud Storage (Silver) -> Modelos de Machine Learning -> Cloud Storage (Gold) -> BigQuery -> Power BI

Estrutura do Projeto:

```
predictops/

01_bronze_para_silver.py

pipeline.py

publish_bigquery.py

publish_silver_bigquery.py

Dockerfile

requirements.txt

models/
├── incidente_d1_d7.py
├── sla_risco.py
├── previsao_turno.py
└── previsao_duracao.py

artifacts/

outputs/
```

## Como rodar?
Para executar todo o pipeline: "python pipeline.py"

Para executar todo o pipeline como um Job do Cloud Run:

1. Build da Imagem Docker (sempre que tiver alteração nos códigos deve-se fazer isso):
```
gcloud builds submit \
    --tag gcr.io/predictops-challenge-2026/predictops
```
2. Atualizar Cloud Run Job (após novo build):
```
gcloud run jobs update predictops-job \
    --image gcr.io/predictops-challenge-2026/predictops \
    --region=southamerica-east1
```
3. Executar Cloud Run Job
```
gcloud run jobs execute predictops-job \
    --region=southamerica-east1
```
4. Ver logs do Job
```
gcloud beta run jobs executions logs read \
    NOME_DA_EXECUCAO \
    --region=southamerica-east1
```

## Buckets Utilizados:

- Bronze: gs://predictops-bronze (armazena LW-DATASET.xlsx -- dataset original)
- Silver gs://predictops-silver (armazena incidentes_tratados.parquet -- dataset tratado)
- Gold gs://predictops-gold (armazena /modelos , /previsoes , /metricas)

## Modelos Desenvolvidos:

#### Modelo 1 - Previsão de Incidentes D+1

- Arquivo: models/incidente_d1_d7.py
- Saída: previsao_incidentes_d1.cs

#### Modelo 2 - Previsão de Incidentes D+7
- Arquivo: models/incidente_d1_d7.py
- Saída: previsao_incidentes_d7.csv

#### Modelo 3 - Risco de Violação de SLA
- Arquivo: models/sla_risco.py
- Saída: previsao_sla.csv

#### Modelo 4 - Previsão de Incidentes por Turno
- Arquivo: models/previsao_turno.py
- Saída: previsao_incidentes_turno.csv

#### Modelo 5 - Previsão de Tempo de Resolução
- Arquivo: models/previsao_duracao.py
- Saída: export_previsao_duracao.csv

## BigQuery:
Dataset criado: predictops_gold

Tabelas:
- incidentes
- previsao_d1
- previsao_d7
- previsao_sla
- previsao_turno
- previsao_duracao
