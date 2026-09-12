"""
Justificativa de Negócio dos Modelos AIOps — Locaweb
Data de referência: 12/12/2025

Explica o valor de cada modelo para NOC, SRE, Operações, Gestão, Diretoria e C-Level.
"""
import streamlit as st
import theme as T
from theme import apply_theme, RED, NAVY_LIGHT

DATA_REF = "12/12/2025"

# ─── dados de conteúdo ────────────────────────────────────────────────────────

MODELOS = [
    {
        "id": "d1",
        "ico": "calendar",
        "titulo": "Previsão D+1 — Volume de Incidentes (Amanhã)",
        "tabela": "previsao_d1",
        "cor": "#3B82F6",
        "objetivo": (
            "Antecipar o volume de incidentes que serão abertos no próximo dia útil "
            "com base em padrões históricos de sazonalidade, dia da semana, datas especiais "
            "e correlação com mudanças de infraestrutura previstas. O modelo permite que "
            "gestores e equipes operacionais se preparem proativamente."
        ),
        "kpis": [
            "Volume de Incidentes (total do dia)",
            "Taxa de OLA — % de atendimentos dentro do prazo",
            "MTTR — Tempo médio de resolução",
            "Utilização de capacidade das equipes designadas",
        ],
        "perspectivas": {
            "NOC / Operadores": (
                "Saber quantos incidentes estão previstos para o dia seguinte permite escalar "
                "a equipe corretamente. Evita surpresas no início do turno e garante que os "
                "operadores entrem preparados para picos de demanda."
            ),
            "SRE": (
                "Apoia decisões de freeze de mudanças em dias de alta previsão, priorizando "
                "estabilidade operacional. Permite correlacionar eventos de deploy com picos "
                "de incidentes previstos."
            ),
            "Operações": (
                "Subsidia o dimensionamento de plantão e o agendamento de manutenções "
                "preventivas fora dos períodos de maior risco projetado."
            ),
            "Gestão": (
                "Habilita planejamento de capacidade de curto prazo com base em dados, "
                "substituindo decisões puramente intuitivas. KPI de acurácia do modelo "
                "acompanha melhoria contínua."
            ),
            "Diretoria": (
                "Visibilidade antecipada de riscos operacionais para o próximo dia. "
                "Contribui para OLA global e redução de custos com horas-extra não planejadas."
            ),
            "C-Level": (
                "Demonstra maturidade AIOps nível 3 (operação preditiva). "
                "Reduz custos operacionais em até 20% ao evitar superdimensionamento de "
                "plantão e resposta reativa a crises. Fortalece o argumento de ROI em IA."
            ),
        },
        "acoes": [
            "Aumentar escala de plantão nos dias com previsão acima do percentil 80",
            "Acionar equipes de suporte especializado de forma antecipada",
            "Suspender mudanças planejadas em dias de previsão crítica",
            "Notificar clientes VIP sobre potencial degradação preventiva",
        ],
        "reducao_custo": (
            "Evita contratação emergencial de suporte extra e horas-extra não planejadas. "
            "Estima-se redução de 15-25% dos custos de plantão ao alinhar escala à previsão."
        ),
        "reducao_risco": (
            "Antecipa riscos de violação de OLA com 24h de antecedência, "
            "permitindo ação proativa antes do impacto ao cliente."
        ),
        "aiops": (
            "Representa a transição do modelo reativo (responder a incidentes) para o modelo "
            "preditivo (antecipar incidentes). Nível 3 do modelo de maturidade AIOps."
        ),
    },
    {
        "id": "d7",
        "ico": "trend",
        "titulo": "Previsão D+7 — Volume Semanal de Incidentes",
        "tabela": "previsao_d7",
        "cor": "#8B5CF6",
        "objetivo": (
            "Projetar o volume de incidentes para os próximos 7 dias, considerando "
            "tendências de médio prazo, janelas de manutenção, sazonalidade semanal "
            "e eventos recorrentes. Oferece visibilidade estratégica para planejamento "
            "de capacidade e negociação de OLA."
        ),
        "kpis": [
            "Volume semanal de incidentes",
            "Taxa de OLA da semana",
            "Backlog de incidentes pendentes",
            "Índice de recorrência por categoria",
        ],
        "perspectivas": {
            "NOC / Operadores": (
                "Planeja escalas semanais e períodos de folga com base na previsão, "
                "evitando subfornecimento em dias críticos."
            ),
            "SRE": (
                "Orienta janelas de manutenção para os dias de menor previsão, "
                "reduzindo o risco de incidentes durante mudanças planejadas."
            ),
            "Operações": (
                "Permite reservar capacidade de atendimento para picos previstos e "
                "otimizar distribuição de carga entre equipes ao longo da semana."
            ),
            "Gestão": (
                "Fundamenta reuniões de S&OP operacional com dados preditivos, "
                "substituindo revisões puramente históricas."
            ),
            "Diretoria": (
                "Antecipa semanas de alta pressão operacional com 7 dias de antecedência, "
                "possibilitando realocação de recursos antes de crises."
            ),
            "C-Level": (
                "Suporta comprometimentos contratuais de OLA com base em previsão "
                "quantitativa, reduzindo penalidades e risco de churn de clientes."
            ),
        },
        "acoes": [
            "Planejar escalas semanais alinhadas à curva de previsão",
            "Agendar janelas de mudança nos vales da curva semanal",
            "Preparar comunicação preventiva para clientes em semanas de alta previsão",
            "Alocar budget de horas-extra antecipadamente",
        ],
        "reducao_custo": (
            "Planejamento de escala semanal reduz custos com banco de horas e "
            "contratação emergencial. Estima-se economia de 10-18% em custos de pessoal operacional."
        ),
        "reducao_risco": (
            "Reduz risco de penalidades de OLA ao antecipar semanas críticas. "
            "Permite renegociação prévia de compromissos com grandes clientes."
        ),
        "aiops": (
            "Eleva o horizonte preditivo de 1 para 7 dias, transitando para a camada "
            "estratégica do AIOps (planejamento de capacidade orientado por dados)."
        ),
    },
    {
        "id": "turno",
        "ico": "clock",
        "titulo": "Previsão por Turno — Granularidade Intradiária",
        "tabela": "previsao_turno",
        "cor": "#F59E0B",
        "objetivo": (
            "Detalhar a previsão de volume de incidentes por turno operacional "
            "(Madrugada, Manhã, Tarde, Noite), permitindo alocação de recursos "
            "com precisão intradiária. Alimenta diretamente o Jornal de Turno e "
            "a passagem de responsabilidade entre operadores."
        ),
        "kpis": [
            "Volume de incidentes por turno",
            "Distribuição de P1/P2 por período",
            "Utilização de capacidade por turno",
            "Taxa de resolução dentro do turno",
        ],
        "perspectivas": {
            "NOC / Operadores": (
                "Ferramenta central do Jornal de Turno: o operador inicia seu turno "
                "sabendo exatamente quantos incidentes são esperados e quais equipes "
                "estarão mais pressionadas. Elimina a 'cegueira no início do turno'."
            ),
            "SRE": (
                "Identifica turnos cronicamente sobrecarregados para propor automações "
                "e reduções de ruído operacional nos períodos críticos."
            ),
            "Operações": (
                "Dimensiona coberturas de escalão por turno com base em dados, "
                "não em intuição do gestor de turno."
            ),
            "Gestão": (
                "Permite comparar desempenho entre turnos e identificar gargalos "
                "estruturais (ex: turno da madrugada consistentemente acima do previsto)."
            ),
            "Diretoria": (
                "Fornece evidência de que a operação é gerida por dados em todas "
                "as camadas, inclusive intradiária — diferencial competitivo."
            ),
            "C-Level": (
                "Dado estratégico para negociação de contratos de OLA 24×7 com "
                "fundamentação quantitativa por faixa horária."
            ),
        },
        "acoes": [
            "Ajustar escala de operadores por turno com base na previsão",
            "Alertar turno seguinte sobre incidentes de alta duração abertos",
            "Priorizar resolução de P1/P2 antes da passagem de turno",
            "Registrar desvios previsto×realizado para retroalimentar o modelo",
        ],
        "reducao_custo": (
            "Otimiza alocação de pessoal por turno, evitando sobredimensionamento "
            "em turnos de baixo volume e subdimensionamento nos picos."
        ),
        "reducao_risco": (
            "Evita que incidentes críticos fiquem sem cobertura adequada durante "
            "turnos de maior demanda, reduzindo risco de violação de OLA noturno."
        ),
        "aiops": (
            "Granularidade intradiária é um dos pilares do AIOps nível 4: "
            "operação contínua orientada por previsão em tempo real."
        ),
    },
    {
        "id": "sla",
        "ico": "alert",
        "titulo": "Previsão de Violação de OLA — Risco por Incidente",
        "tabela": "previsao_sla",
        "cor": "#EF4444",
        "objetivo": (
            "Calcular, para cada incidente em aberto, a probabilidade de violação "
            "do OLA antes da resolução, com base no tempo decorrido, prioridade, "
            "equipe designada, histórico de atendimento e complexidade estimada. "
            "Habilita intervenção cirúrgica antes da violação acontecer."
        ),
        "kpis": [
            "% de cumprimento de OLA (meta: 95%)",
            "Número de violações de OLA no período",
            "Probabilidade média de violação por equipe",
            "Taxa de quase-violações (>75%) evitadas",
        ],
        "perspectivas": {
            "NOC / Operadores": (
                "Exibe em tempo real quais incidentes estão prestes a violar o OLA. "
                "Permite que o operador re-priorize sua fila de atendimento de forma "
                "cirúrgica, focando nos casos de maior risco."
            ),
            "SRE": (
                "Identifica padrões de equipes/produtos que sistematicamente geram "
                "alto risco de violação, direcionando esforços de automação e melhoria "
                "de processos onde o impacto é maior."
            ),
            "Operações": (
                "Permite escalar incidentes de alto risco antes da violação, "
                "acionando backups e recursos adicionais de forma proativa."
            ),
            "Gestão": (
                "Dashboard de risco de OLA em tempo real substitui relatórios "
                "post-mortem. Decisões baseadas em probabilidade futura, não em "
                "histórico passado."
            ),
            "Diretoria": (
                "Visualização clara do risco operacional atual. Permite comunicação "
                "proativa com clientes sobre incidentes de alto risco antes do impacto."
            ),
            "C-Level": (
                "Reduz penalidades contratuais de OLA. Cada violação evitada representa "
                "economia direta em créditos e risco de churn. ROI mensurável e imediato."
            ),
        },
        "acoes": [
            "Escalar imediatamente incidentes com probabilidade >90%",
            "Notificar gestor da equipe para incidentes com probabilidade 75-90%",
            "Redirecionar incidentes para equipes menos sobrecarregadas",
            "Comunicar proativamente o cliente sobre incidente de alto risco",
        ],
        "reducao_custo": (
            "Cada violação de OLA evitada elimina créditos financeiros, penalidades "
            "contratuais e risco de churn. Modelos similares em mercado geram ROI "
            "de 3-8x o investimento em dados e ML em 12 meses."
        ),
        "reducao_risco": (
            "Reduz diretamente a taxa de violação de OLA. Empresas que implementam "
            "modelos preditivos de OLA reportam redução de 30-50% nas violações."
        ),
        "aiops": (
            "Caso de uso mais maduro do AIOps: inteligência aplicada diretamente "
            "à tomada de decisão operacional em tempo real. Marco de maturidade nível 4."
        ),
    },
    {
        "id": "duracao",
        "ico": "gauge",
        "titulo": "Previsão de Duração — Tempo de Resolução por Incidente",
        "tabela": "previsao_duracao",
        "cor": "#10B981",
        "objetivo": (
            "Estimar o tempo total de resolução de cada incidente no momento da "
            "abertura, com base em características do chamado, equipe designada, "
            "produto afetado e padrões históricos similares. Permite gerenciar "
            "expectativas de clientes e priorizar a fila de atendimento."
        ),
        "kpis": [
            "MTTR — Tempo médio de resolução",
            "Distribuição de duração por prioridade",
            "Backlog de incidentes de longa duração",
            "Taxa de resolução no primeiro contato (FCR)",
        ],
        "perspectivas": {
            "NOC / Operadores": (
                "Identifica no início do atendimento quais incidentes têm alta "
                "probabilidade de durar mais que o OLA, permitindo escalonamento "
                "antecipado para especialistas."
            ),
            "SRE": (
                "Aponta produtos e categorias com duração sistematicamente acima "
                "do esperado — candidatos prioritários para runbooks, automações "
                "e melhorias de observabilidade."
            ),
            "Operações": (
                "Permite alocar os incidentes de maior duração prevista para "
                "operadores sênior logo na abertura, otimizando o uso do capital humano."
            ),
            "Gestão": (
                "Acompanha tendência de MTTR e identifica deteriorações antes "
                "que se reflitam em violações de OLA. KPI preditivo de eficiência operacional."
            ),
            "Diretoria": (
                "Métrica estratégica de eficiência: redução de MTTR representa "
                "menos tempo de indisponibilidade para o cliente e menor custo operacional."
            ),
            "C-Level": (
                "Cada hora de redução no MTTR médio se traduz em disponibilidade "
                "adicional para o cliente. Impacto direto em NPS, churn e receita recorrente."
            ),
        },
        "acoes": [
            "Alocar incidentes de alta duração prevista para especialistas sênior",
            "Acionar time de escalonamento antes de atingir 70% do OLA para incidentes longos",
            "Identificar incidentes similares já resolvidos como base para aceleração",
            "Gerar alertas automáticos quando duração real superar previsão",
        ],
        "reducao_custo": (
            "Redução de MTTR diminui custo por incidente. Em operações de grande escala, "
            "cada 10% de redução no MTTR representa impacto significativo no custo/hora de operação."
        ),
        "reducao_risco": (
            "Incidentes de longa duração não gerenciados são a principal causa de "
            "violações de OLA. O modelo reduz esse risco ao tornar a duração previsível."
        ),
        "aiops": (
            "Integra o ciclo preditivo completo: prevê volume (D+1/D+7), "
            "prevê risco (OLA) e agora prevê duração — completando o trio "
            "de inteligência operacional do AIOps."
        ),
    },
    {
        "id": "cluster_inc",
        "ico": "layers",
        "titulo": "Clusterização Operacional — Agrupamento de Incidentes",
        "tabela": "clusters_incidentes",
        "cor": "#6366F1",
        "objetivo": (
            "Agrupar automaticamente incidentes por similaridade operacional "
            "(produto, categoria, equipe, comportamento temporal), identificando "
            "grupos de incidentes relacionados que podem ter uma causa raiz comum. "
            "Suporta análise de causa raiz e identificação de problemas recorrentes."
        ),
        "kpis": [
            "Taxa de incidentes agrupados (vs. incidentes isolados)",
            "Número de clusters ativos por turno",
            "Percentual de clusters com causa raiz identificada",
            "Redução de tempo de RCA (Root Cause Analysis)",
        ],
        "perspectivas": {
            "NOC / Operadores": (
                "Identifica incidentes que são sintomas do mesmo problema, "
                "evitando trabalho duplicado. O operador vê 'cluster de 12 incidentes' "
                "em vez de 12 tickets isolados, focando na causa raiz."
            ),
            "SRE": (
                "Ferramenta central para Problem Management: clusters recorrentes "
                "indicam problemas sistêmicos que merecem investimento em solução definitiva."
            ),
            "Operações": (
                "Prioriza a triagem de incidentes: resolver a causa raiz de um cluster "
                "fecha múltiplos tickets simultaneamente, multiplicando a eficiência."
            ),
            "Gestão": (
                "Relatórios de clusters permitem identificar os 'problemas crônicos' "
                "da operação e priorizá-los no roadmap de melhorias."
            ),
            "Diretoria": (
                "Visibilidade de padrões recorrentes que afetam múltiplos clientes, "
                "fundamentando decisões de investimento em infraestrutura."
            ),
            "C-Level": (
                "Problemas crônicos não resolvidos são o principal driver de churn. "
                "A clusterização acelera a identificação e eliminação desses problemas."
            ),
        },
        "acoes": [
            "Criar Problem Records para clusters com >5 incidentes na última semana",
            "Alocar engenheiro SRE para análise de causa raiz dos clusters maiores",
            "Correlacionar clusters com mudanças recentes para identificar causa",
            "Monitorar dissolução de clusters como confirmação de resolução definitiva",
        ],
        "reducao_custo": (
            "Resolver a causa raiz de um cluster elimina múltiplos incidentes futuros. "
            "Uma causa raiz endereçada pode prevenir dezenas de tickets recorrentes."
        ),
        "reducao_risco": (
            "Incidentes repetitivos sem causa raiz identificada são um risco contínuo "
            "de violação de OLA. A clusterização acelera a eliminação desse risco."
        ),
        "aiops": (
            "Machine Learning não supervisionado aplicado a dados operacionais. "
            "Representa a camada de inteligência diagnóstica do AIOps."
        ),
    },
    {
        "id": "cluster_nlp",
        "ico": "brain",
        "titulo": "Clusterização NLP — Temas Emergentes nas Descrições",
        "tabela": "cluster_nlp",
        "cor": "#EC4899",
        "objetivo": (
            "Aplicar Processamento de Linguagem Natural (NLP) às descrições livres "
            "dos incidentes para identificar temas emergentes, detectar anomalias "
            "semânticas e descobrir padrões que não aparecem nas categorizações "
            "estruturadas. Complementa a clusterização operacional com inteligência textual."
        ),
        "kpis": [
            "Número de temas emergentes identificados por semana",
            "Taxa de categorização automática vs. manual",
            "Tempo médio de identificação de novo problema via NLP",
            "Precisão do modelo de classificação semântica",
        ],
        "perspectivas": {
            "NOC / Operadores": (
                "Identifica no texto dos tickets padrões que os campos estruturados "
                "não capturam — por exemplo, múltiplos operadores descrevendo 'lentidão "
                "no painel de controle' em palavras diferentes, mas referindo-se ao "
                "mesmo problema."
            ),
            "SRE": (
                "Detecta anomalias semânticas (temas incomuns surgindo) que podem "
                "indicar um novo tipo de falha emergindo antes de aparecer nos alertas "
                "de monitoramento tradicional."
            ),
            "Operações": (
                "Reduz a necessidade de categorização manual: o modelo classifica "
                "automaticamente os tickets em temas, liberando tempo dos analistas "
                "para atividades de maior valor."
            ),
            "Gestão": (
                "Relatórios de temas emergentes substituem análise qualitativa manual "
                "de grandes volumes de texto, tornando a análise escalável."
            ),
            "Diretoria": (
                "Detecção precoce de novos tipos de incidentes permite resposta "
                "estratégica antes que o problema escale para um evento de crise."
            ),
            "C-Level": (
                "Capacidade de processamento semântico de dados não-estruturados "
                "é um diferencial competitivo de IA. Demonstra sofisticação tecnológica "
                "e liderança em inovação operacional no setor de hosting."
            ),
        },
        "acoes": [
            "Monitorar surgimento de novos temas não mapeados como sinal de alerta",
            "Usar temas NLP para enriquecer a base de conhecimento (KB)",
            "Correlacionar temas emergentes com mudanças de produto/infraestrutura",
            "Treinar o modelo com novas descrições para melhoria contínua",
        ],
        "reducao_custo": (
            "Automação da categorização semântica reduz horas de trabalho manual "
            "em análise de tickets. Em operações de escala, representa economia "
            "significativa de FTE em análise qualitativa."
        ),
        "reducao_risco": (
            "Detecção precoce de temas emergentes reduz o 'tempo cego' entre "
            "o surgimento de um novo tipo de problema e sua identificação e resposta."
        ),
        "aiops": (
            "NLP em dados operacionais representa a fronteira do AIOps: "
            "extração de inteligência de dados não-estruturados. "
            "Marco de maturidade nível 5 — AIOps cognitivo."
        ),
    },
]


# ─── painel principal ─────────────────────────────────────────────────────────

def render_justificativa_negocio():
    apply_theme()

    T.hero("Justificativa de Negócio dos Modelos AIOps",
           "Valor estratégico e operacional de cada modelo. "
           f"Referência: <code>{DATA_REF}</code>.")

    st.markdown("""
    Esta seção apresenta a justificativa detalhada de cada modelo preditivo da plataforma **predictops**,
    explicando o problema operacional que resolve, os KPIs impactados e o valor gerado para cada nível
    da organização — de operadores NOC até C-Level.
    """)

    # ── abas por modelo ───────────────────────────────────────────────────
    abas = st.tabs([m["titulo"].split(" — ")[0] for m in MODELOS])

    for aba, modelo in zip(abas, MODELOS):
        with aba:
            _render_modelo(modelo)


def _render_modelo(m: dict):
    cor = m["cor"]
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {cor}18 0%, transparent 100%);
            border-left: 4px solid {cor};
            border-radius: 8px;
            padding: 1rem 1.2rem;
            margin-bottom: 1rem;
        ">
            <span style="display:inline-flex;align-items:center;gap:.6rem;font-size:1.5rem;
                       font-weight:680;letter-spacing:-.02em;color:{cor};">
                {T.icon(m["ico"], 26, cor, 1.7)}{m['titulo']}</span><br/>
            <code style="color:#6B7280; font-size:0.85rem;">BigQuery: {m['tabela']}</code>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Objetivo
    T.section("Objetivo Operacional", ico="chart")
    st.info(m["objetivo"])

    # KPIs
    T.section("KPIs Impactados", ico="chart")
    kpi_cols = st.columns(min(len(m["kpis"]), 4))
    for i, kpi in enumerate(m["kpis"]):
        with kpi_cols[i % 4]:
            st.markdown(
                f"""
                <div style="
                    background:#F8FAFC; border:1px solid #E5E7EB;
                    border-top:3px solid {cor};
                    border-radius:8px; padding:0.8rem 1rem;
                    font-size:0.85rem; color:#374151; min-height:60px;
                ">
                    {T.icon('target', 14, '#6B7280')} {kpi}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("")

    # Perspectivas por audiência
    T.section("Valor por Audiência", ico="users")
    ICONES_ABA = list(m["perspectivas"].keys())
    tabs_persp = st.tabs(ICONES_ABA)
    for tab_p, key in zip(tabs_persp, ICONES_ABA):
        with tab_p:
            st.markdown(m["perspectivas"][key])

    st.divider()

    # Ações recomendadas + impacto
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        T.section("Ações Operacionais Recomendadas", ico="target")
        for acao in m["acoes"]:
            st.markdown(f"- {acao}")

    with col_b:
        T.section("Redução de Custos", ico="chart")
        st.markdown(
            f"""
            <div style="
                background:#ECFDF5; border:1px solid #6EE7B7;
                border-radius:8px; padding:1rem;
                font-size:0.9rem; color:#065F46;
            ">
                {m['reducao_custo']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_c:
        T.section("Redução de Riscos", ico="alert")
        st.markdown(
            f"""
            <div style="
                background:#FFF7ED; border:1px solid #FCD34D;
                border-radius:8px; padding:1rem;
                font-size:0.9rem; color:#92400E;
            ">
                {m['reducao_risco']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")
    T.section("Contribuição para Maturidade AIOps", ico="chart")
    st.markdown(
        f"""
        <div style="
            background:#EFF6FF; border:1px solid #BFDBFE;
            border-radius:8px; padding:1rem;
            font-size:0.9rem; color:#1E40AF;
        ">
            {m['aiops']}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
