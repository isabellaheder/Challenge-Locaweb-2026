# PredictOps 360

**Antecipe o futuro, proteja o presente.**

Challenge Locaweb · FIAP — *Artificial Intelligence e Deep Learning Application* · Equipe Dataway

---

## Visão Geral

O **PredictOps 360** é uma plataforma de inteligência operacional que usa Inteligência
Artificial, Machine Learning e Analytics avançado para transformar dados históricos de
incidentes em **previsões, insights e recomendações acionáveis**.

Ao centralizar análise preditiva, monitoramento operacional e acesso inteligente à
informação, a solução capacita equipes técnicas e gestores a tomarem decisões mais
rápidas, proativas e orientadas por dados — aumentando a eficiência operacional e
reduzindo riscos ao negócio.

Na prática, a plataforma responde três perguntas que um NOC faz todo dia:

| Pergunta | O que a plataforma entrega |
|---|---|
| **Quanto vem?** | Volume previsto de incidentes para o dia seguinte, para a semana e para cada turno |
| **O que vai estourar?** | Quais chamados têm risco de violar o SLA, enquanto ainda dá tempo de agir |
| **Onde agir primeiro?** | O que causa os chamados, separando ruído automatizável de problema real |

**Base do estudo:** 122.543 incidentes de infraestrutura, de janeiro de 2023 a dezembro
de 2025.

---

## Estrutura do repositório

O repositório segue a ordem natural do trabalho: entender o desafio, tratar o dado,
investigar, modelar, industrializar e entregar na tela.

| Pasta / arquivo | O que tem dentro |
|---|---|
| **`Regras_Gerais_Challenge_Locaweb_Fev_2026.pdf`** | Enunciado e regras do desafio proposto pela Locaweb. Ponto de partida. |
| **`LW-DATASET.xlsx`** | Dataset original entregue pela Locaweb, sem tratamento. |
| **`Tratamento Dados/`** | Limpeza, padronização e *feature engineering*. Gera o `LW-DATASET-TRATADO`, que é a base usada por todo o resto do projeto. Inclui o dicionário de dados tratados. |
| **`Explicacao-Salto-Incidentes/`** | Investigação do salto de volume a partir de set/2025. A conclusão mudou a forma de modelar — ver [Achados](#achados-do-estudo). |
| **`Modelos/`** | Notebooks de treino, avaliação e comparação com baseline dos oito modelos. É aqui que vivem as métricas citadas neste README. |
| **`Job-Pipeline-GCP/`** | Industrialização: o pipeline que roda no Google Cloud. Lê o dado, executa ETL, treina, gera as previsões e carrega tudo no BigQuery, orquestrado por Cloud Run Job + Cloud Scheduler. |
| **`Solucao-streamlit/`** | **A aplicação.** Todo o front-end em Streamlit: painéis, jornal de turno, NL2SQL e assistentes de IA. Tem [README próprio](Solucao-streamlit/README.md) com instruções de build, run no Docker, variáveis de ambiente e estrutura do código. |
| **`Sprint1/`** | Entrega da Sprint 1 — análise exploratória e primeiras hipóteses. |
| **`Sprint3/`** | Entrega da Sprint 3 — modelagem preditiva e documentação da disciplina. |

### Por onde começar a leitura

1. `Regras_Gerais_...pdf`: o que foi pedido
2. `Tratamento Dados/`: como o dado chegou e como ficou
3. `Explicacao-Salto-Incidentes/`: o achado que condicionou a modelagem
4. `Modelos/`: o que foi treinado e com que resultado
5. `Job-Pipeline-GCP/`: como isso vira rotina automatizada
6. `Solucao-streamlit/`: como o usuário final consome tudo

> **Quer só rodar a plataforma?** Vá direto para
> [`Solucao-streamlit/README.md`](Solucao-streamlit/README.md). Lá está o
> `docker build`, o `docker run`.

---

## Funcionalidades

### 1. Painel NOC: a operação do dia
Monitoramento em tempo real para o operador. Sete abas cobrindo a fila do dia
(abertos × resolvidos), a matriz de risco por prioridade, demanda por tipo de trabalho,
tipos de problema, confiabilidade e reincidência (MTBF por item de configuração, recaída
em 24 h, backlog de causa raiz), ritmo e sazonalidade, e um semáforo de confiança dos
modelos.

**Usuário:** operadores.

### 2. Jornal de Turno 
Tudo recortado pelo dia e pelo turno escolhido. O gráfico principal mostra o que segue
aberto no fim do turno, separado por situação de prazo, com a lista por incidente e o
tempo restante previsto. Fecha com um resumo executivo gerado por IA, pronto para colar
no registro de passagem.

**Usuário:** gestores e operadores.

### 3. Painel Gerencial
Ordenado por valor de negócio: exposição ao risco por equipe, projeções D+1 e D+7, modos
de falha, SLA realizado, carga por equipe e produto, e quanto do volume dá para eliminar.

**Usuário:** gestores.

### 4. Consultas SQL em linguagem natural (NL2SQL)
O usuário pergunta em português, o Gemini gera a consulta SQL, a query roda sobre os
dados e a resposta volta com tabela, gráfico e análise. **O SQL gerado fica visível**,
nada de caixa-preta. Tira a fila de pedidos de dados de cima do time técnico.

**Usuário:** gestores e operadores.

### 5. Chatbot: assistente de IA
Dois assistentes com prompts distintos: um operacional (reincidência, risco do turno) e
um executivo (tendência, dimensionamento de equipe). Ambos consultam os dados antes de
responder, em vez de opinar sobre o nada.

**Usuário:** gestores e operadores.

---

## Modelos da solução

Oito modelos em produção. **Todos foram comparados com um baseline**, e onde o baseline
venceu, ele foi mantido.

### Previsão de volume de incidentes (D+1 e D+7)
Gradient Boosting Regressor.

| Horizonte | MAPE do modelo | MAPE do baseline | MAE |
|---|---|---|---|
| D+1 (dia seguinte) | **13,6%** | 20,0% | 106 |
| D+7 (semana seguinte) | **16,1%** | 20,8% | 128 |

Num dia de 780 incidentes, isso é uma margem de ±106 chamados contra ±164 do baseline.
É o que permite dimensionar a escala antes do pico, e não depois.

### Previsão de volume por turno
Gradient Boosting Regressor · MAPE **22,0%** contra 31,5% do baseline · MAE 49,2.

O erro é maior que o diário porque a janela é menor: um pico que atravessa a virada entra
na conta do turno seguinte.

### Previsão de violação do KPI (risco de SLA)
Gradient Boosting Classifier.

- **Recall 0,92** no threshold 0,3 — 92% das violações são sinalizadas antes de acontecer
- **ROC AUC 0,75**
- Entre os incidentes de maior risco, a taxa de violação é cerca de **14× a média da carteira**

O corte é ajustável: em 0,3 o alerta é sensível mas pouco denso; em 0,75 a fila fica curta
e muito mais densa.

### Previsão de duração do atendimento
Random Forest Regressor · 70% das previsões a menos de 30 minutos da duração real · 85%
dentro de 2 horas · erro mediano de 6 minutos · MAPE 24% contra 37% do baseline.

### Cluster de incidentes (K-means)
Três regimes operacionais, por atributos do chamado:

| Regime | Volume | Perfil |
|---|---|---|
| Ruído de monitoramento | 77.719 (63%) | 100% aberto por automação, 71% P4 |
| Operação geral | 31.494 (26%) | 51% monitoramento / 49% manual, 71% P3 |
| Chamados especializados | 13.330 (11%) | 79% monitoramento, 29% P2 |

### Previsão de volume por cluster
Cada regime tem seu próprio modelo:

| Regime | Modelo escolhido (D+1) | MAE |
|---|---|---|
| Ruído de monitoramento | **persistência** venceu o ML | 99 |
| Operação geral | gradient boosting | 27 |
| Chamados especializados | gradient boosting | 18 |

O ruído é gerado por automação, com volume quase constante: não há sazonalidade a
aprender, e forçar ML ali só adicionaria variância.

### Cluster de incidentes pela descrição (NLP)
Oito tipos de problema extraídos do texto do chamado: ruído operacional, capacidade de
armazenamento, disco I/O sobrecarregado, indisponibilidade por ping, falta de memória
swap, sobrecarga de processamento, infraestrutura de virtualização e saturação de workers
Apache.

---

## Achados do estudo

**1. O salto de volume em set/2025 não foi degradação de infraestrutura.**
O campo *Aberto por = Monitoramento* passou de ~59% para ~95%, concentrado em um único
produto, categoria e grupo. O alerta "Check Application Monitoring" saltou de 47 para
~6.590 incidentes — cerca de 140×. Foi mudança de observabilidade, não piora do ambiente.
Sem essa leitura, qualquer modelo treinado no período anterior quebraria em silêncio.
Detalhes em [`Explicacao-Salto-Incidentes/`](Explicacao-Salto-Incidentes).

**2. O risco não está onde está o volume.**
Indisponibilidade por ping é 4% do volume, mas 95% desses chamados são de prioridade alta
— contra 13% na média da base. Disco cheio tem duas vezes e meia mais volume e quase
nenhum chamado crítico. Priorizar por quantidade coloca o time no problema errado.

**3. Quase 4 em cada 10 chamados não deveriam existir.**
Dos 93.687 incidentes classificados pelo NLP, 23.174 são saturação de recurso (disco,
swap, CPU, I/O — que deveriam virar capacity planning, não incidente) e 14.867 são
chamados duplicados, abertos com vínculo a um incidente pai. Cerca de 1,6 mil pertencem
aos dois grupos, então o volume endereçável fica em torno de 39%. O que sobra — 55.646 —
é a operação de fato, e é esse número que deveria dimensionar a escala do time.

---

## Arquitetura

```
LW-DATASET.xlsx
      │
      ▼
GCS bronze ──► GCS silver ──► Cloud Run Job ──► Python: ETL, treino e previsão
  (bruto)       (tratado)     (diário, via           │
                              Cloud Scheduler)       ▼
                                            BigQuery · predictops_gold
                                                     │
                                 ┌───────────────────┴──────────────────┐
                                 ▼                                      ▼
                        Streamlit App                          Gemini / Vertex AI
                  painéis, jornal e gráficos                NL2SQL e assistentes de IA
```

| Camada | Tecnologia |
|---|---|
| Data lake | Google Cloud Storage (bronze / silver) |
| Orquestração | Cloud Run Jobs + Cloud Scheduler |
| Processamento e ML | Python (scikit-learn, pandas) |
| Data warehouse | BigQuery — dataset `predictops_gold` |
| IA generativa | Gemini via Vertex AI |
| Interface | Streamlit |

O pipeline está em Job-Pipeline-GCP; a aplicação, em
Solucao-streamlit. A interface **apenas lê**.

---

## Como rodar

O passo a passo completo (Docker, execução local, deploy no Cloud Run, variáveis de
ambiente e credenciais) está em
[`Solucao-streamlit/README.md`](Solucao-streamlit/README.md). Em resumo:

```bash
cd Solucao-streamlit
cp .env.example .env          # preencha com suas credenciais

docker build -t predictops360 .

docker run --rm -p 8080:8080 \
  --env-file .env \
  -v "$(pwd)/bigquery-credentials.json:/app/bigquery-credentials.json:ro" \
  -v "$(pwd)/gcp-credentials.json:/app/gcp-credentials.json:ro" \
  predictops360
```

Acesse <http://localhost:8080>.

---

## Sobre a data de referência

A plataforma abre ancorada em uma **data de referência operacional** (09/12/2025) em vez
de usar a data de hoje. Isso é proposital: o dataset é congelado e termina em 31/12/2025,
então usar `datetime.now()` abriria a tela com zero incidentes.

Em produção, a data seria `now()` — mas o que sustenta isso não é a data e sim a
ingestão: extração incremental do ITSM a cada poucos minutos, previsão gravada com data
de execução separada da data alvo, e risco de SLA **repontuado enquanto o incidente
estiver aberto** (um chamado com 20% de risco às 9h pode estar com 80% às 15h).

---

## Limitações conhecidas

| Limitação | Próximo passo |
|---|---|
| O modelo de risco pontua só parte dos incidentes — há turnos sem chamado avaliado | Pontuar todos os incidentes elegíveis |
| No threshold de 0,3 o alerta é sensível mas pouco denso: a precisão é baixa | Calibrar o corte pelo custo do alarme falso e publicar precisão ao lado do recall |
| O D+7 erra mais que o D+1 e perde precisão nos picos | Features de calendário e tratamento explícito de feriados |
| A carga é de arquivo, não incremental | Ingestão por `updated_at`, com upsert no BigQuery |
| O login da aplicação não autentica de verdade | IAP ou provedor de identidade na frente da app |
| A mudança de monitoramento em set/2025 desloca o histórico | Marcador de regime no treino e alerta de drift |

---

## Equipe — Dataway

| Integrante | RM |
|---|---|
| Angelo Rabello | RM564338 |
| Isabella Heder | RM561300 |
| João Dalessio | RM561050 |
| Milena Oliveira | RM558913 |
| Paulo Luchini | RM561477 |

FIAP · Artificial Intelligence e Deep Learning Application · Challenge Locaweb 2026
