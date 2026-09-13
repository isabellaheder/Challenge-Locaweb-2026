# Modelos - PredictOps 360

Todos os notebooks de Machine Learning do projeto. Cada um resolve **uma** pergunta de
negócio, gera os CSVs que alimentam o `predictops_gold` no BigQuery e é comparado com um
baseline (onde o baseline venceu, ele foi mantido)

**Base de entrada:** `LW-DATASET-TRATADO.xlsx` (122.543 incidentes, jan/2023 a dez/2025),
produzida em [`../Tratamento Dados/`](../Tratamento%20Dados).

---

## Os notebooks

| # | Notebook | Pergunta que responde | Saída |
|---|---|---|---|
| 1 | [`d1_d7.ipynb`](d1_d7.ipynb) | Quantos incidentes chegam **amanhã** e **daqui a 7 dias**? | `previsao_incidentes_d1/d7.csv` |
| 2 | [`perda_ola.ipynb`](perda_ola.ipynb) | Quais chamados vão **violar o OLA**? | `export_previsoes_kpi.csv` |
| 3 | [`cluster.ipynb`](cluster.ipynb) | Que **tipo de trabalho** a operação recebe? | 3 regimes operacionais |
| 4 | [`previsao_incidentes_turno.ipynb`](previsao_incidentes_turno.ipynb) | Quantos incidentes chegam **em cada turno**? | `previsao_incidentes_turno.csv` |
| 5 | [`previsao_duracao.ipynb`](previsao_duracao.ipynb) | **Quanto tempo** cada chamado vai levar? | `export_previsao_duracao.csv` |
| 6 | [`incident_clustering_nlp.ipynb`](incident_clustering_nlp.ipynb) | **O que** está quebrando, segundo a descrição do chamado? | 8 tipos de problema |
| 7 | [`previsao_d1_d7_por_cluster.ipynb`](previsao_d1_d7_por_cluster.ipynb) | Quantos incidentes chegam **de cada regime**? | `previsao_d1/d7_por_cluster.csv` |

Os notebooks 1 e 2 produzem os rótulos que o 5 consome. O resto é independente.

---

## 1. `d1_d7.ipynb` - volume diário

**Gradient Boosting Regressor** sobre a série diária agregada, com lags e médias móveis.
Split temporal.

| Horizonte | MAPE | Baseline | MAE |
|---|---|---|---|
| D+1 | **13,6%** | 20,0% | 106 |
| D+7 | **16,1%** | 20,8% | 128 |

Num dia de 780 incidentes, 13,6% de erro é uma margem de ±106 chamados, contra ±164 do
baseline.

## 2. `perda_ola.ipynb` - risco de violação de OLA

**Gradient Boosting Classifier** sobre os incidentes elegíveis a KPI
(`Entrou para KPI? = SIM`). Target: `kpi_violado`.

O alvo é **extremamente desbalanceado** (cerca de 1% de violações), o que exige três
cuidados registrados no notebook:

1. `Undersampling` para equilibrar as classes no treino ----- o teste foi feito na base desbalanceada (para ver se o modelo realmente aprendeu padrão mesmo com undersampling)
2. Remoção das features que vazam o resultado (`KPI Violado?`, `kpi_nao_aplicavel` e
   derivadas) ---> só existem depois que o chamado fecha.
3. Threshold ajustado (testados 0,2 / 0,3 / 0,4), e não o 0,5 padrão.

| Métrica | Valor |
|---|---|
| Recall (threshold 0,3) | **0,92** |
| ROC AUC | 0,75 |

**Ressalva honesta:** o threshold de 0.3 trouxe um valor alto para recall, mas trouxe junto, valores falsos positivos. Por isso, 
fica a critério da Locaweb a escolha de outros valores de threshold baseado nas prioridades da empresa.

## 3. `cluster.ipynb` - regimes operacionais

**K-Means** sobre os atributos do incidente (prioridade, produto, categoria, subcategoria,
grupo designado, item de configuração, aberto por, hora, dia da semana, mês).

Standard Scaler e agrupamento de categorias para melhorar a quantidade de colunas (pós get dummies)

**K = 3**, escolhido por Elbow + Silhouette (0,4648).

| Cluster | Nome | Volume | Perfil |
|---|---|---|---|
| 0 | **Ruído de monitoramento** | 77.719 (63,4%) | 100% aberto por automação, 71% P4 |
| 1 | **Operação geral** | 31.494 (25,7%) | 49% manual, P3 dominante |
| 2 | **Cauda crítica** | 13.330 (10,9%) | 29% P2, categorias específicas |

## 4. `previsao_incidentes_turno.ipynb` - volume por turno

A unidade vira **dia × turno** (Madrugada 0-6h, Manhã 6-12h,
Tarde 12-18h, Noite 18-24h). 

Os lags são calculados **dentro do turno**: `lag_1` é o mesmo
turno de ontem, não o turno anterior.

Série completada com zero nas combinações sem incidente === dia sem chamado é observação
válida, não dado faltante

| Escopo | MAPE | Baseline |
|---|---|---|
| Geral | **22,0%** | 31,5% |
| Madrugada | 24% | — |
| Manhã | 22% | — |
| Tarde | 21% | — |
| Noite | 21% | — |

O erro é maior que o diário porque a janela é menor: um pico que atravessa a virada do
turno cai na conta do turno seguinte.

## 5. `previsao_duracao.ipynb` - duração do atendimento

**Random Forest Regressor**

target transformada em **log1p**, porque a duração tem
cauda longuíssima (a maioria fecha em minutos, alguns ficam semanas em aberto) e o modelo
treinado na escala bruta é dominado pelos outliers. 

A previsão volta com `expm1`.

`DummyRegressor` entra como baseline.

| Métrica | Valor |
|---|---|
| Previsões a menos de 30 min do real | **70%** |
| Previsões dentro de 2 h do real | **85%** |
| Erro mediano | 6 minutos |
| MAPE | 24% (baseline: 37%) |

## 6. `incident_clustering_nlp.ipynb` - tipos de problema

**TF-IDF + TruncatedSVD + MiniBatchKMeans** sobre a `Descrição resumida`. Inclui lista de
stopwords personalizada (termos operacionais que aparecem em todo chamado e não separam
nada) e um score composto de `silhouette`, `davies_bouldin` e `calinski_harabasz` para
escolher a configuração (em vez de olhar uma métrica só)

Resultado: 8 tipos de problema, nomeados pelas palavras-chave dominantes de cada grupo.

| Tipo | % da base | Prioridade dominante |
|---|---|---|
| Ruído operacional | +60% | P3 |
| Capacidade de armazenamento | 9,7% | P4 |
| Disco I/O sobrecarregado | 8% | P3 e P4 |
| Indisponibilidade (ping) | 4% | **P2** |
| Falta de memória swap | 3% | P4 |
| Sobrecarga de processamento | 3% | P3 |
| Infraestrutura de virtualização | 2% | P4 |
| Apache e saturação de workers | 2% | P3 |

**O achado:** Indisponibilidade por ping é 4% do volume, mas **95% desses chamados são
P2**, contra 13% na média da base. Disco cheio tem 2,5× mais volume e quase nenhum
chamado crítico. **O risco não está onde está o volume**, e é por isso que priorizar a
fila por quantidade coloca o time no problema errado.

## 7. `previsao_d1_d7_por_cluster.ipynb` — volume por regime

Decompõe a previsão nos três regimes do `cluster.ipynb`.

- **Validação rolling-origin:** 4 janelas de 30 dias dentro do treino, com retreino a cada
  janela. O campeão é escolhido pelo MAE médio dessas janelas.
- **Teste cego:** últimos 20% da série, nunca vistos na seleção.
- **9 candidatos**, incluindo 3 estimadores ingênuos. Se o ML não bate "repetir ontem", ele
  não vai para produção.

| Regime | Campeão D+1 | MAE (validação) | vs melhor ingênuo |
|---|---|---|---|
| Ruído de monitoramento | **Naive_hoje** (persistência) | 60,6 | ML perde por 112% |
| Operação geral | GB_huber | 22,4 | ML ganha 38,8% |
| Cauda crítica | RandomForest | 14,6 | ML ganha 27,6% |

**O achado técnico:** o ML só aprende onde existe padrão de demanda humana. O ruído é
dirigido por mudanças de configuração de monitoramento == não há sazonalidade a capturar,
só nível a acompanhar, e um estimador simples faz isso melhor.

A soma das três previsões dá MAE 120,50 em D+1, contra 122,38 do modelo único global. Em
D+7 as duas empatam. Ou seja: **mesmo nível de erro, com três números acionáveis no lugar
de um número cego.**

---

## Regras seguidas nos notebooks
- **Baseline obrigatório.** Toda métrica aparece ao lado da referência ingênua. Um MAE de
  27 não diz nada sozinho; 27 contra 19,8 da persistência diz tudo.
- **Recorte a partir de 2025-01-01** nos modelos de série, para não treinar em cima de um
  período com processo de abertura diferente.

## O que sai daqui e para onde vai

| CSV gerado | Tabela no BigQuery | Consumido por |
|---|---|---|
| `previsao_incidentes_d1.csv` | `previsao_d1` | Painel NOC, Painel Gerencial |
| `previsao_incidentes_d7.csv` | `previsao_d7` | Painel Gerencial |
| `previsao_incidentes_turno.csv` | `previsao_turno` | Jornal de Turno |
| `previsao_d1_por_cluster.csv` | `previsao_d1_por_cluster` | Painel NOC |
| `previsao_d7_por_cluster.csv` | `previsao_d7_por_cluster` | Painel NOC |
| `metricas_previsao_por_cluster.csv` | `metricas_previsao_por_cluster` | aba Confiança dos Modelos |
| `export_previsoes_kpi.csv` | `previsao_OLA` | Painel NOC, Jornal, Painel Gerencial |
| `export_previsao_duracao.csv` | `previsao_duracao` | Jornal de Turno |
| `clusters_incidentes.csv` | `clusters_incidentes` | os três painéis |
| `incident_clusters.csv` | `cluster_nlp` | Painel NOC, Painel Gerencial |
