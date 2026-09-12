# PredictOps 360

**Antecipe o futuro, proteja o presente.**

Plataforma de inteligência operacional para NOC. Lê a base histórica de incidentes de
infraestrutura (122.543 chamados, jan/2023 a dez/2025), roda oito modelos de Machine
Learning sobre ela e devolve três coisas na tela: **quanto vem**, **o que vai estourar**
e **onde agir primeiro**.

Projeto acadêmico da disciplina *Artificial Intelligence e Deep Learning Application*

FIAP, equipe Dataway

| | |
|---|---|
| **Frontend** | Streamlit |
| **Dados** | Google BigQuery (`predictops_gold`) |
| **IA generativa** | Gemini via Vertex AI |
| **Deploy** | Docker / Cloud Run |

---

## Sumário

- O que a plataforma faz
- Como rodar
- Configuração
- Arquitetura
- Os modelos
- O que encontramos nos dados
- Estrutura do código
- Sobre a data de referência

---

## O que a plataforma faz

São cinco módulos, divididos entre dois perfis de acesso (operador e gestor).

### 1. Painel NOC: operação do dia
Sete abas: visão do dia, risco e SLA, demanda por tipo de trabalho, tipos de problema
(NLP), confiabilidade e reincidência, ritmo e sazonalidade, confiança dos modelos.
Responde "o que está acontecendo agora e o que vai estourar".

Destaques: fila do dia (abertos × resolvidos da mesma coorte), matriz de risco por
prioridade, queima do orçamento de erro do SLO, MTBF por item de configuração, taxa de
recaída em 24 h e um backlog de causa raiz com ação sugerida por tipo de problema.

### 2. Jornal de Turno: a passagem
Tudo recortado pelo dia e pelo turno selecionado. O gráfico principal mostra o que segue
aberto no fim do turno, separado por situação de prazo, com a lista por incidente e o
tempo restante previsto. Existe em duas leituras: operador (com cross-filter e tabela por
número de incidente) e gestor (leitura direta).

### 3. Painel Gerencial: decisão
Ordenado por valor de negócio: exposição ao risco por equipe, projeções D+1 e D+7, modos
de falha (regimes e tipos de problema), SLA realizado, carga por equipe e produto, e
quanto do volume dá para eliminar.

### 4. Pesquisas em linguagem natural (NL2SQL)
O usuário pergunta em português, o Gemini gera o SQL, a consulta roda sobre um SQLite em
memória carregado a partir do BigQuery, e a resposta volta com tabela, gráfico e análise.
O SQL gerado fica visível.

### 5. Assistente de IA
Dois assistentes com prompts distintos: um operacional (reincidência, risco do turno) e
um executivo (tendência, dimensionamento). Ambos consultam os dados antes de responder,
em vez de opinar sobre o nada.

### 6. Justificativa dos modelos
Uma tela dedicada a mostrar métrica, baseline e por que cada modelo foi escolhido.

---

## Como rodar

### Docker (recomendado)

```bash
# 1. clone e entre na pasta
git clone <url-do-repo>
cd predict-ops

# 2. configure as variáveis
cp .env.example .env
#    edite o .env e coloque as credenciais (ver seção Configuração)

# 3. build
docker build -t {nome da sua pasta -- Solucao-Frontend} .

# 4. run
docker run --rm -p 8080:8080 \
  --env-file .env \
  -v "$(pwd)/bigquery-credentials.json:/app/bigquery-credentials.json:ro" \
  -v "$(pwd)/gcp-credentials.json:/app/gcp-credentials.json:ro" \
  predictops360
```

Abra <http://localhost:8080>.

As chaves entram por volume, montadas como somente leitura. **Não as copie para dentro da
imagem** — o `.dockerignore` e o `.gitignore` existem exatamente para isso.

No Windows (PowerShell), troque `$(pwd)` por `${PWD}`.

### Local, sem Docker

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # e preencha
streamlit run app.py
```

Abre em <http://localhost:8501>.

### Deploy no Cloud Run

```bash
PROJECT=predictops-challenge-2026
REGION=us-central1

gcloud builds submit --tag gcr.io/$PROJECT/predictops360

gcloud run deploy predictops360 \
  --image gcr.io/$PROJECT/predictops360 \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --service-account predictops-plataforma@$PROJECT.iam.gserviceaccount.com \
  --set-env-vars BQ_PROJECT=$PROJECT,BQ_DATASET=predictops_gold,GCP_LOCATION=$REGION
```

No Cloud Run, use a service account do serviço em vez de montar arquivos de chave

### Acesso

A tela de login pede usuário, senha e perfil (Operador NOC ou Gestor). **O login é
decorativo**: serve só para escolher qual conjunto de telas aparece.

---

## Configuração

Copie `.env.example` para `.env` e preencha. As variáveis que importam:

| Variável | Para quê | Padrão |
|---|---|---|
| `BQ_PROJECT` | projeto que hospeda e fatura as consultas | `predictops-challenge-2026` |
| `BQ_DATASET` | dataset com as tabelas | `predictops_gold` |
| `BQ_CREDENTIALS_PATH` | chave de serviço com acesso ao BigQuery | `bigquery-credentials.json` |
| `BQ_LOCATION` | região do dataset; deixe vazio se for multi-região US | vazio |
| `GCP_PROJECT_ID` | projeto do Vertex AI | `predictops-challenge-2026` |
| `GCP_LOCATION` | região do Vertex AI | `us-central1` |
| `VERTEX_CREDENTIALS_PATH` | chave de serviço do Gemini | `gcp-credentials.json` |
| `LOCAL_DATASET_PATH` | Excel usado como fallback se o BigQuery cair | `LW-DATASET-TRATADO.xlsx` |
| `META_MTTR_H` | meta de MTTR em horas, usada nas linhas de referência | `48` |
| `MTTR_MAX_H` | teto de sanidade: resoluções acima disso saem da média | `720` |

Constantes operacionais que **não** vêm dos dados e devem ser ajustadas ao contrato real
estão em `config.py`:

```python
SLA_HORAS_POR_PRIORIDADE = {"P1": 4.0, "P2": 4.0, "P3": 12.0, "P4": 24.0, "P5": 96.0}
```

### Tabelas esperadas no BigQuery

| Tabela | Conteúdo |
|---|---|
| `incidentes` | base histórica tratada |
| `previsao_d1` / `previsao_d7` | volume previsto e real por dia |
| `previsao_turno` | volume previsto e real por turno |
| `previsao_sla` | probabilidade de violação de KPI por incidente |
| `previsao_duracao` | duração prevista e real por incidente |
| `clusters_incidentes` | cluster K-means de cada incidente |
| `cluster_nlp` | cluster de NLP da descrição |
| `previsao_d1_por_cluster` / `previsao_d7_por_cluster` | previsão decomposta por regime |
| `metricas_previsao_por_cluster` | MAE, RMSE, R², MAPE e modelo escolhido |

Se o BigQuery estiver indisponível, a aplicação cai para o Excel local e mostra um aviso
no topo de toda tela indicando de onde veio o dado. O carregamento é cacheado por 30
minutos (`st.cache_data(ttl=1800)`).

---

## Arquitetura

```
Excel / ITSM
     │
     ▼
GCS bronze  ──►  GCS silver  ──►  Cloud Run Job (diário)  ──►  Python
  (bruto)         (tratado)         orquestra o pipeline       ETL + treino
                                                                    │
                                                                    ▼
                                                          BigQuery predictops_gold
                                                                    │
                                          ┌─────────────────────────┴───────────┐
                                          ▼                                     ▼
                                  Streamlit (esta app)                 Gemini / Vertex AI
                                  painéis e jornal                     NL2SQL + assistentes
```

O Cloud Scheduler dispara o Cloud Run Job todo dia: ele trata os dados, cria o silver, lê o silver, treina os modelos,
gera os CSVs de saída e carrega tudo no BigQuery. A aplicação só lê — nenhuma escrita
parte da interface.

---

## Os modelos

Oito modelos, todos comparados com um baseline. Onde o baseline venceu, ele foi mantido.

### 1. Previsão de demanda: Gradient Boosting Regressor

| Horizonte | MAPE do modelo | MAPE do baseline | MAE |
|---|---|---|---|
| D+1 (dia seguinte) | **13,6%** | 20,0% | 106 |
| D+7 (semana seguinte) | **16,1%** | 20,8% | 128 |
| Por turno | **22,0%** | 31,5% | 49,2 |

O erro por turno é maior porque a janela é menor: um pico que atravessa a virada entra na
conta do turno seguinte.

### 2. Previsão por regime (cluster K-means)

| Regime | Volume | Modelo escolhido (D+1) | MAE |
|---|---|---|---|
| Ruído de monitoramento | 77.719 (63%) | **persistência** — venceu o ML | 99 |
| Operação geral | 31.494 (26%) | gradient boosting | 27 |
| Chamados especializados | 13.330 (11%) | gradient boosting | 18 |

O ruído é gerado por automação, com volume quase constante. Não há sazonalidade a
aprender, e forçar ML ali só adicionaria variância — por isso o estimador simples ficou.

### 3. Risco de violação de SLA — Gradient Boosting Classifier

- **Recall 0,92** no threshold 0,3 = 92% das violações são sinalizadas antes de acontecer
- **ROC AUC 0,75**
- Entre os incidentes de maior risco, a taxa de violação é cerca de **14× a média da
  carteira**

O threshold é ajustável. Em 0,3 o alerta é sensível mas pouco denso (a base viola ~1% das
vezes, então há muito falso positivo); em 0,75 a fila fica curta e muito mais densa.
Calibrar esse corte pelo custo do alarme falso é um próximo passo declarado.

### 4. Duração do atendimento — Random Forest Regressor

- 70% das previsões ficam a menos de 30 minutos da duração real
- 85% ficam dentro de 2 horas
- Erro mediano de 6 minutos; MAPE de 24% contra 37% do baseline

### 5. Clusterização

- **K-means** sobre os atributos do incidente → 3 regimes operacionais
- **NLP** sobre a descrição resumida → 8 tipos de problema (falta de swap, disco cheio,
  I/O sobrecarregado, CPU/iowait, indisponibilidade por ping, virtualização, workers
  Apache e ruído operacional)

---

## O que encontramos nos dados

**1. O salto de volume em set/2025 não foi degradação de infraestrutura.**
O campo "Aberto por = Monitoramento" passou de ~59% para ~95%, concentrado em um único
produto, categoria e grupo. O alerta "Check Application Monitoring" saltou de 47 para
~6.590 incidentes. Foi mudança de observabilidade, não piora do ambiente. Sem essa
leitura, qualquer modelo treinado no período anterior quebraria.

**2. O risco não está onde está o volume.**
Indisponibilidade por ping é 4% do volume, mas 95% desses chamados são de prioridade
alta, contra 13% na média da base. Disco cheio tem duas vezes e meia mais volume e quase
nenhum chamado crítico. Priorizar por quantidade coloca o time no problema errado.

**3. Quase 4 em cada 10 chamados não deveriam existir.**
Dos 93.687 incidentes que o NLP classificou: 23.174 são saturação de recurso (disco,
swap, CPU, I/O... que deveriam virar capacity planning, não incidente) e 14.867 são
chamados duplicados, abertos com vínculo a um incidente pai. Cerca de 1,6 mil estão nos
dois grupos, então o volume endereçável fica em torno de 39%. O que sobra — 55.646 — é a
operação de fato, e é esse número que deveria dimensionar a escala.

> "Operação de fato" é uma definição nossa (total classificado menos os dois grupos), não
> uma métrica de mercado.

---

## Estrutura do código

```
predict-ops/
├── app.py                    # roteamento, sessão e navegação
├── config.py                 # variáveis de ambiente e constantes operacionais
├── bq_loader.py              # conexão com BigQuery, cache e fallback local
├── data_loader.py            # SQLite em memória para o NL2SQL
├── data_prep.py              # camada de preparo: temas, regimes, SLA, recortes
├── viz_helpers.py            # biblioteca de gráficos e componentes
├── theme.py                  # paleta, tipografia e componentes visuais
├── gemini_service.py         # chamadas ao Vertex AI, geração de SQL, assistentes
├── kpi_context.py            # contexto de KPIs entregue aos assistentes
├── views/
│   ├── login.py
│   ├── operador_painel.py    # Painel NOC
│   ├── operador_jornal.py    # Jornal de Turno (operador e gestor)
│   ├── gestor_painel.py      # Painel Gerencial
│   ├── operador_ia.py
│   ├── gestor_ia.py
│   ├── pesquisas_nl2sql.py
│   └── justificativa_negocio.py
├── Dockerfile
├── requirements.txt
└── .env.example
```

**Onde mexer para cada coisa:**

- adicionar ou alterar um gráfico → `viz_helpers.py` (o componente) e a `view` correspondente
- mudar como um dado é agregado → `data_prep.py`
- trocar cor, fonte ou espaçamento → `theme.py`
- apontar para outro dataset ou tabela → `config.py` / `.env`

---

## Sobre a data de referência (leia antes de julgar)

A plataforma utiliza uma **data de referência operacional**
(`REF_DATE`, hoje `09/12/2025`), e não em `datetime.now()`. Como o dataset é estático e termina em 31/12/2025, 
usar o dia corrente faria o painel exibir métricas zeradas. Por isso, adotamos 09/12/2025 como um "hoje" 
simulado dentro do período válido dos dados.

Em produção, bastaria substituir a REF_DATE pela data atual. Para isso, seriam 
implementados alguns ajustes: ingestão contínua de dados do ITSM, separação entre 
data de execução e data prevista para manter o histórico de acurácia, atualização 
contínua do risco de SLA enquanto os incidentes permanecem abertos, garantia de uso 
apenas de informações disponíveis no momento da previsão e monitoramento do desempenho 
dos modelos com retreinamento quando necessário.

Nesse cenário, o painel abriria sempre com dados em tempo real, mantendo o seletor 
de datas apenas para análises históricas.

---


## Equipe

Angelo Rabello (RM564338) · Isabella Heder (RM561300) · João Dalessio (RM561050) ·
Milena Oliveira (RM558913) · Paulo Luchini (RM561477)

FIAP - 2026 (Challenge Locaweb)
