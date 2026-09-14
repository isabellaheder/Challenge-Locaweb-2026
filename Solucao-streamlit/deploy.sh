#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Deploy do PredictOps 360 no Cloud Run.
# Rode de dentro da pasta da aplicação (onde está o Dockerfile e o app.py).
#   bash deploy.sh
# ---------------------------------------------------------------------------
set -e

PROJETO="predictops-challenge-2026"        # <-- confira o ID do seu projeto
REGIAO="southamerica-east1"                # São Paulo
SERVICO="predictops360"
SA="predictops-app"                        # nome da service account da aplicação
SA_EMAIL="${SA}@${PROJETO}.iam.gserviceaccount.com"

echo ">> Projeto: $PROJETO | Região: $REGIAO"
gcloud config set project "$PROJETO"

echo ">> 1/4 Habilitando as APIs necessárias..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  bigquery.googleapis.com \
  aiplatform.googleapis.com

echo ">> 2/4 Criando a service account da aplicação (ignore o erro se já existir)..."
gcloud iam service-accounts create "$SA" \
  --display-name="PredictOps 360 - aplicacao Cloud Run" || true

echo ">> 3/4 Concedendo as permissões mínimas..."
for PAPEL in roles/bigquery.dataViewer roles/bigquery.jobUser roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJETO" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$PAPEL" --condition=None --quiet
done

echo ">> 4/4 Build e deploy (o Cloud Build monta a imagem, não precisa de Docker local)..."
gcloud run deploy "$SERVICO" \
  --source . \
  --region "$REGIAO" \
  --platform managed \
  --allow-unauthenticated \
  --service-account "$SA_EMAIL" \
  --port 8080 \
  --memory 2Gi \
  --cpu 1 \
  --timeout 3600 \
  --session-affinity \
  --min-instances 1 \
  --max-instances 3 \
  --set-env-vars "BQ_PROJECT=${PROJETO},BQ_DATASET=predictops_gold,BQ_LOCATION=${REGIAO},GCP_PROJECT_ID=${PROJETO},GCP_LOCATION=us-central1"

echo
echo ">> Pronto. URL pública:"
gcloud run services describe "$SERVICO" --region "$REGIAO" --format="value(status.url)"