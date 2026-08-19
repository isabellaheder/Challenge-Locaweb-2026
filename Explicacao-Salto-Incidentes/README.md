# Investigação do Salto de Incidentes na Locaweb 

### Objetivo
O objetivo desta análise foi investigar a causa do aumento abrupto no volume de incidentes registrados pela operação da Locaweb, identificando padrões, tendências e possíveis fatores responsáveis pela mudança observada a partir de setembro de 2025.

### Contexto
Durante a análise temporal dos incidentes foi identificado um comportamento anômalo a partir de setembro de 2025.

O maior pico ocorreu em:
- **22/09/2025**
- **1.431 incidentes em um único dia**
<img width="859" height="393" alt="addbbc8a-0ece-413b-b60a-eefb1614b7a6" src="https://github.com/user-attachments/assets/a131c841-e4cf-4484-bf5b-87de223ef927" />

### Evidências

Origem dos Incidentes:

| Período | Monitoramento | Manual |
|----------|----------|----------|
| Antes | 58,91% | 41,09% |
| Setembro | 92,80% | 7,20% |
| Depois | 95,34% | 4,66% |

O aumento está fortemente associado a incidentes gerados automaticamente por sistemas de monitoramento.

- A análise dos produtos mostrou uma concentração extrema em MONITORING_AUTO
- A categoria mais impactada foi INFRA_Monitoramento
- A maioria dos incidentes registrados após o salto apresentava status Sem Intervenção
  - Lembrando que: nas regras a maioria dos incidentes com status "Sem Intervenção" está associada ao campo "Aberto por = Monitoramento"
- A análise por grupo designado identificou forte concentração na Team14


### Perfil que explica salto:

Foi realizada uma análise conjunta considerando os seguintes critérios:

- Produto = `MONITORING_AUTO`
- Grupo = `Team14`
- Categoria = `INFRA_Monitoramento`
- Status = `Sem Intervenção`
- Aberto por = `Monitoramento`

> Resultado: 15.131 incidentes
>> Representando: 70,18% de todos os incidentes do período

### Principais Alertas Encontrados
forte concentração em poucos tipos de alerta

| Descrição | Ocorrências |
|------------|------------:|
| Check Application Monitoring | 6.524 |
| High bandwidth >60% at least 15m | 1.837 |
| Apache Busy Workers | 756 |
| Free disk space <10% | 606 |
| Unavailable by ICMP ping | 538 |

Comparando os períodos:

- Check Application Monitoring: antes tinham 47 incidentes, durante 6.590 (crescimento superior a 140x)

## Conclusão
A análise indica que o aumento abrupto de incidentes observado a partir de setembro de 2025 não ocorreu de forma distribuída entre produtos, categorias e equipes.

Os resultados mostram que o crescimento foi fortemente concentrado em incidentes relacionados ao produto **MONITORING_AUTO**, à categoria **INFRA_Monitoramento**, atribuídos à **Team14**, abertos automaticamente por sistemas de **Monitoramento** e encerrados como **Sem Intervenção**.

Além disso, a maior parte dos registros está associada a poucos alertas recorrentes, especialmente **Check Application Monitoring** e **High bandwidth >60% at least 15m**, que apresentaram crescimento expressivo em relação aos períodos anteriores.

Dessa forma, as evidências sugerem que o salto observado está mais relacionado a alterações nos processos de monitoramento, observabilidade ou automação da abertura de incidentes do que a uma degradação generalizada da infraestrutura da organização.
