# Visão Geral

O PredictOps é uma plataforma preditiva para operações de TI construída na Google Cloud Platform utilizando arquitetura Bronze, Silver e Gold.

A solução processa dados de incidentes, treina modelos de Machine Learning, gera previsões e publica os resultados no BigQuery para consumo pelo Power BI.

## Pipeline
Cloud Storage (Bronze) -> Cloud Storage (Silver) -> Modelos de Machine Learning -> Cloud Storage (Gold) -> BigQuery -> Power BI

### Estrutura do Projeto: 

> **IMPORTANTE**: todos os códigos apresentados nesta pasta são uma versão mais rápida e direta dos códigos criados dentro dos **notebooks python** dentro deste repositório git

```
predictops/

    01_bronze_para_silver.py      # tratamento dos dados (nulos, criação de flags etc)
    
    pipeline.py                   # orquestrador principal que executa todos os scripts da solução em sequência
    
    publish_bigquery.py           # publica os resultados dos modelos (arquivos CSV da pasta outputs) no BigQuery
    
    publish_silver_bigquery.py    # publica o dataset tratado da camada Silver (incidentes_tratados.parquet) na tabela incidentes do BigQuery
    
    Dockerfile                    # definição da imagem Docker utilizada pelo Cloud Run Job
    
    requirements.txt              # dependências necessárias para execução do pipeline
    
    models/    
    ├── incidente_d1_d7.py        # previsão de volume de incidentes para D+1 e D+7
    ├── sla_risco.py              # classificação de risco de violação de SLA/OLA
    ├── previsao_turno.py         # previsão de quantidade de incidentes por turno
    └── previsao_duracao.py       # previsão de tempo de resolução dos incidentes
    └── cluster.py                # segmentação dos incidentes utilizando K-Means
    
    artifacts/                    # artefatos gerados pelos modelos
    ├── modelo_d1.joblib
    ├── modelo_d7.joblib
    ├── modelo_sla.joblib
    ├── modelo_turno.joblib
    ├── modelo_duracao.joblib
    └── modelo_cluster.joblib
    
    outputs/                       # resultados gerados pelos modelos
    ├── previsao_incidentes_d1.csv
    ├── previsao_incidentes_d7.csv
    ├── previsao_sla.csv
    ├── previsao_incidentes_turno.csv
    ├── export_previsao_duracao.csv
    └── clusters_incidentes.csv
```

## Como rodar?
Dentro do Cloud Shell Editor:
- Para executar todo o pipeline: "python pipeline.py"

Para executar todo o pipeline como um >>**Job do Cloud Run**<<:

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
Exemplo:

<img width="600" alt="image" src="https://github.com/user-attachments/assets/592c520f-7a08-4f09-98a0-4e08f3ffa3b2" />
<img width="800" alt="image" src="https://github.com/user-attachments/assets/0be67ec3-754f-444c-b77a-f789d9d962b5" />

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

#### Modelo 6 - Clusterização de Incidentes
- Arquivo: cluster.py
- Saída: clusters_incidentes.csv

## BigQuery:
Dataset criado: predictops_gold
<img width="800" alt="image" src="https://github.com/user-attachments/assets/5b628ea4-3b2c-45ce-b141-c4cb13ec0694" />

