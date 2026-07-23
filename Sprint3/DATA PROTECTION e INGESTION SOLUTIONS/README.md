## Disciplina: DATA PROTECTION & INGESTION 

### Estratégia de Backup e Recuperação do Ambiente de Dados

O grupo deverá definir uma estratégia de backup para os dados utilizados no Challenge.

A estratégia deverá contemplar, no mínimo: 
- backup full
- backup incremental
- política de retenção
- periodicidade das cópias
- local de armazenamento (Data Lake, Object Storage, cloud storage ou equivalente)

O grupo deverá justificar tecnicamente a estratégia adotada, considerando a proteção do
ambiente analítico e a continuidade da solução de AIOps proposta para a locaweb, com foco
na previsão de incidentes, no monitoramento de tendências operacionais e na disponibilidade
dos dados para análise e tomada de decisão.

Relacionar a estratégia de backup ao cenário do projeto, explicando como os dados poderão
ser restaurados em caso de falha.

________
### Pipeline de Ingestão Orquestrado (Apache Airflow, KNIME ou serviços equivalentes em nuvem) (30 pontos):

O grupo deverá implementar um pipeline de ingestão utilizando Apache Airflow, KNIME ou
serviços equivalentes em nuvem, a critério do grupo.

O pipeline deverá contemplar no mínimo as seguintes etapas:

- extração dos dados
- transformação / limpeza
- validação
- carga para ambiente analítico

O grupo deverá entregar:
- código da DAG (.py), no caso do Airflow
- workflow (.knwf) ou evidência do fluxo, no caso do KNIME
- scripts, pipelines, queries, configurações ou evidências técnicas equivalentes, no caso de
serviços em nuvem

Apresentar evidências visuais da execução com sucesso. 
A escolha da ferramenta deverá ser tecnicamente justificada.
___________
### Estratégia de Recovery e Reprocessamento (25 pontos)
- Simular um cenário de falha e evidenciar a recuperação, utilizando os recursos da ferramenta
escolhida.
- Explicar como a estratégia garante continuidade da ingestão e disponibilidade dos dados para
o Challenge.
____________
### Relatório Final de Evidências – PDF (20 pontos)
- Nome do arquivo: evidencias-sprint3-rm9999.pdf
    - Onde rm9999 corresponde ao RM do representante do grupo.

O relatório deverá conter, no mínimo:
- nome completo e RM dos participantes em ordem alfabética
- estratégia de backup adotada
- justificativa técnica
- evidências do pipeline (Airflow, KNIME ou serviço equivalente em nuvem)
- logs e evidências de recovery
- prints do fluxo em execução
- explicação executiva final do grupo (máximo 5 linhas), descrevendo como a solução
garante disponibilidade, segurança e continuidade do projeto

