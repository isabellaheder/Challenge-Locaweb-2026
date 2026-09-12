import json
import os
import re
import streamlit as st
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

from data_loader import run_sql_query, descrever_schema, tabelas_disponiveis
from config import GCP_LOCATION, VERTEX_CREDENTIALS_PATH, GCP_PROJECT_ID

# ==============================================================================
# CONFIGURAÇÃO E AUTENTICAÇÃO VERTEX AI (GCP NATIVO)
# ==============================================================================
# Credenciais do Vertex AI (Gemini) — separadas da chave usada no BigQuery.
CREDENTIALS_PATH = VERTEX_CREDENTIALS_PATH

# Modelos padrão suportados pelo Vertex AI
VERTEX_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

@st.cache_resource(show_spinner=False)
def init_vertex_ai():
    """Inicializa o Vertex AI obtendo o Project ID real diretamente do JSON."""
    project_id = None

    if os.path.exists(CREDENTIALS_PATH):
        try:
            with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                project_id = data.get("project_id")
        except Exception:
            pass

    if not project_id:
        project_id = os.getenv("GCP_PROJECT_ID", GCP_PROJECT_ID)

    if not project_id:
        raise ValueError(
            "Não foi possível identificar o Project ID. Verifique se o arquivo 'gcp-credentials.json' está na pasta raiz do projeto."
        )

    if os.path.exists(CREDENTIALS_PATH):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH
        credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
        vertexai.init(project=project_id, location=GCP_LOCATION, credentials=credentials)
    else:
        vertexai.init(project=project_id, location=GCP_LOCATION)

    return project_id


def call_gemini(prompt: str, system_instruction: str = None,
                temperature: float = 0.2, max_output_tokens: int = 2048) -> str:
    """Executa chamadas no Vertex AI testando os modelos disponíveis.

    `max_output_tokens` é parametrizável porque os modelos 2.5 consomem parte do
    orçamento com raciocínio interno: com o teto baixo a resposta volta cortada
    no meio (foi o que quebrava a geração de SQL, devolvendo um bloco markdown
    sem a crase de fechamento).
    """
    init_vertex_ai()

    generation_config = GenerationConfig(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )

    last_error = None
    for model_name in VERTEX_MODELS:
        try:
            if system_instruction:
                model = GenerativeModel(
                    model_name=model_name,
                    system_instruction=[system_instruction]
                )
            else:
                model = GenerativeModel(model_name=model_name)

            response = model.generate_content(prompt, generation_config=generation_config)
            texto = getattr(response, "text", None) if response else None
            if texto and texto.strip():
                return texto
        except Exception as e:
            print(f"Modelo {model_name} falhou:")
            print(repr(e))
            last_error = e

    raise RuntimeError(f"Erro ao consultar modelos Vertex AI ({VERTEX_MODELS}): {str(last_error)}")


# ==============================================================================
# GERAÇÃO DE SQL COMPARTILHADA (usada pelo NL2SQL e pelos assistentes de chat)
# ==============================================================================
_SQL_PROIBIDO = re.compile(
    r"\b(drop|delete|update|insert|alter|create|replace|attach|pragma|vacuum)\b",
    re.IGNORECASE)


def extrair_sql(texto: str) -> str:
    """Extrai a consulta SQL da resposta do modelo, tolerando qualquer formato.

    Trata os casos que quebravam a execução:
      * bloco markdown sem crase de fechamento (resposta truncada) — o antigo
        fallback removia as crases e sobrava a palavra `sql` na primeira linha,
        produzindo exatamente o erro `near "sql": syntax error`;
      * marcação com outro rótulo (```SQL, ```sqlite) ou sem rótulo;
      * texto explicativo antes ou depois da consulta.
    """
    if not texto:
        raise ValueError("O modelo não retornou conteúdo para a consulta.")

    t = texto.strip()
    m = re.search(r"```[a-zA-Z]*\s*(.*?)```", t, re.DOTALL)
    if m:
        t = m.group(1)
    else:
        t = t.replace("```", " ")

    # Remove um rótulo de linguagem que tenha sobrado sozinho na primeira linha.
    t = re.sub(r"^\s*(sql|sqlite|sql_query)\s*[\r\n:]+", "", t, flags=re.IGNORECASE)

    # Começa na primeira cláusula de leitura, descartando qualquer preâmbulo.
    inicio = re.search(r"\b(WITH|SELECT)\b", t, re.IGNORECASE)
    if not inicio:
        raise ValueError(f"Nenhuma consulta SELECT encontrada na resposta do modelo: {texto[:200]}")
    t = t[inicio.start():]

    # Corta no primeiro ponto e vírgula — o que vier depois é comentário do modelo.
    if ";" in t:
        t = t[:t.index(";")]
    sql = t.strip()

    # Verifica comandos de escrita ignorando o conteúdo de literais de texto,
    # senão um filtro legítimo (LIKE '%update%') seria bloqueado.
    sem_literais = re.sub(r"'[^']*'", "''", sql)
    if _SQL_PROIBIDO.search(sem_literais):
        raise ValueError("A consulta gerada contém um comando de escrita e foi bloqueada.")
    return sql


def _gerar_sql(user_prompt: str, erro_anterior: str = None, sql_anterior: str = None) -> str:
    """Gera uma consulta SQL SQLite a partir de uma pergunta em linguagem natural.

    O schema descreve TODAS as tabelas materializadas do `predictops_gold`
    (incidentes + tabelas de previsão), não só `incidentes` — sem isso, perguntas
    sobre D+1, D+7, risco de SLA, duração prevista ou clusters não tinham onde
    ser respondidas.

    Quando `erro_anterior` é informado, o modelo recebe a consulta que falhou e a
    mensagem do SQLite para se corrigir.
    """
    schema_txt = descrever_schema()
    tabelas = ", ".join(tabelas_disponiveis())

    correcao = ""
    if erro_anterior:
        correcao = f"""
    ATENÇÃO — a consulta abaixo foi executada e falhou. Corrija-a.
    Consulta anterior:
    {sql_anterior}
    Erro retornado pelo SQLite: {erro_anterior}
    """

    prompt_eng = f"""
    Você é um especialista em SQL e Engenharia de Dados.
    Converta a pergunta do usuário em UMA consulta SQL válida no dialeto SQLite.

    Tabelas disponíveis (nomes e colunas exatamente como estão no banco):
    {schema_txt}

    Regras estritas:
    1. Responda com a consulta SQL e NADA MAIS: sem markdown, sem crases, sem
       explicação, sem rótulo de linguagem. A primeira palavra da sua resposta
       deve ser SELECT ou WITH.
    2. Apenas leitura (SELECT/WITH). Nunca DROP, DELETE, UPDATE, INSERT ou CREATE.
    3. Use somente as tabelas e colunas listadas acima: {tabelas}.
    4. Escolha a tabela certa para a pergunta: volume futuro do dia seguinte →
       previsao_d1; da semana → previsao_d7; por turno → previsao_turno; risco de
       violação de SLA por incidente, produto ou equipe → previsao_sla; tempo de
       resolução previsto → previsao_duracao; agrupamento de incidentes →
       clusters_incidentes ou cluster_nlp. Fatos históricos → incidentes.
    5. Para juntar previsão com atributos do incidente, faça JOIN pelo número do
       incidente (ex.: previsao_sla.Numero_Incidente = incidentes.Numero).
    6. Contagens e rankings usam GROUP BY, ORDER BY ... DESC e LIMIT N.
    7. Ao filtrar colunas textuais (Produto, Categoria, Item_de_configuracao,
       Descricao_resumida), use LIKE com '%'.
    8. Prioridades válidas em `incidentes`: '1 - Crítica', '2 - Alta', '3 - Média',
       '4 - Baixa', '5 - Muito Baixa'. Coluna de SLA: KPI_Violado ('SIM', 'NAO',
       'NAO_APLICAVEL').
    9. Datas estão em texto ISO ('YYYY-MM-DD HH:MM:SS'). A base é histórica:
       expressões como "hoje", "ontem" ou "últimas 24 horas" são relativas à data
       MAIS RECENTE da coluna, nunca à data atual do sistema.
       Ex.: WHERE Aberto >= (SELECT datetime(MAX(Aberto), '-24 hours') FROM incidentes).
    {correcao}
    Pergunta do Usuário: "{user_prompt}"
    """

    resposta = call_gemini(prompt_eng, max_output_tokens=4096)
    return extrair_sql(resposta)


def gerar_e_executar_sql(user_prompt: str, tentativas: int = 2):
    """Gera a consulta, executa e — se o SQLite recusar — devolve o erro ao modelo
    para uma tentativa de correção. Retorna (sql, dataframe)."""
    erro = sql = None
    for _ in range(max(1, tentativas)):
        sql = _gerar_sql(user_prompt, erro_anterior=erro, sql_anterior=sql)
        try:
            return sql, run_sql_query(sql)
        except Exception as e:
            erro = str(e)
    raise RuntimeError(f"A consulta gerada não pôde ser executada. Última tentativa:\n{sql}\nErro: {erro}")


def _consultar_dados_reais(user_prompt: str) -> str:
    """Gera e executa uma consulta SQL relacionada à pergunta do usuário e devolve os dados
    reais encontrados em texto, para embasar as respostas do chat em fatos da base."""
    try:
        sql_query, df_res = gerar_e_executar_sql(user_prompt)
    except Exception as e:
        return (f"(Não foi possível consultar a base automaticamente. Motivo: {e}. "
                f"Tabelas disponíveis para consulta: {', '.join(tabelas_disponiveis())}.)")

    if df_res.empty:
        return f"Consulta executada:\n{sql_query}\n\nNenhum registro encontrado para esses critérios."

    return (
        f"Consulta executada no dataset predictops_gold:\n{sql_query}\n\n"
        f"Resultado ({len(df_res)} linha(s), mostrando até 15):\n"
        f"{df_res.head(15).to_string(index=False)}"
    )


def _formatar_historico(history: list, max_turnos: int = 6) -> str:
    """Formata as últimas trocas da conversa para dar memória ao assistente entre perguntas."""
    if not history:
        return "(início da conversa)"
    trechos = []
    for msg in history[-max_turnos:]:
        papel = "Analista/Gestor" if msg["role"] == "user" else "Assistente"
        trechos.append(f"{papel}: {msg['content']}")
    return "\n".join(trechos)


# ==============================================================================
# ASSISTENTE OPERACIONAL (NOC)
# ==============================================================================
def ask_operator_assistant(prompt: str, context_kpis: dict, history: list = None) -> str:
    """Assistente operacional voltado para NOC e suporte técnico. A cada pergunta, gera e
    executa uma consulta SQL real na base de incidentes (via _consultar_dados_reais) e usa
    o histórico da conversa para manter contexto entre turnos."""
    dados_reais = _consultar_dados_reais(prompt)
    historico_txt = _formatar_historico(history)

    system_instruction = f"""
    Você é o Assistente Virtual Operacional do Predict Ops (Locaweb AIOps).
    Seu papel é apoiar analistas de NOC, operadores de turno e supervisores com respostas técnicas,
    ágeis e diretas — interpretando dados reais e recomendando ações, e não apenas descrevendo
    procedimentos genéricos.

    Visão geral histórica da base, calculada agora do dataset predictops_gold
    (referência, não é o dado específico da pergunta):
    - Data operacional de referência: {context_kpis.get('data_referencia', '—')}
    - Total de incidentes na base: {context_kpis.get('total_incidentes', 0)}
    - Incidentes com SLA violado (histórico total): {context_kpis.get('kpi_violados', 0)}
    - Principais equipes historicamente: {context_kpis.get('top_equipes', 'Team14, Team12, Team06')}
    - Principais produtos historicamente: {context_kpis.get('top_produtos', 'MONITORING_AUTO, lhco, email')}

    Diretrizes:
    1. Baseie sua resposta nos "Dados reais consultados" informados a seguir, citando os números encontrados.
    2. Se a consulta não retornou dados suficientes ou falhou, diga isso claramente em vez de generalizar.
    3. Sobre reincidência, baseie-se no histórico do mesmo IC ou descrição resumida trazido pela consulta.
    4. Cite os limites de SLA por prioridade quando for relevante (P1/P2: até 4h, P3: até 12h, P4: até 24h, P5: até 96h).
    5. Use o histórico da conversa para manter continuidade entre perguntas.
    6. NUNCA invente números: se o dado não veio da consulta, diga que não veio.
    7. Seja direto e técnico, e finalize com uma sugestão de ação ou procedimento operacional.
    """

    prompt_completo = f"""
    Histórico recente da conversa:
    {historico_txt}

    Dados reais consultados na base de incidentes para esta pergunta:
    {dados_reais}

    Pergunta atual do analista: "{prompt}"
    """
    try:
        return call_gemini(prompt_completo, system_instruction)
    except Exception as err:
        return f"Erro ao consultar o Vertex AI:\n\n{str(err)}"


# ==============================================================================
# ASSISTENTE GERENCIAL (ESTRATÉGICO)
# ==============================================================================
def ask_manager_assistant(prompt: str, context_kpis: dict, history: list = None) -> str:
    """Assistente executivo e estratégico. Também consulta dados reais da base a cada
    pergunta, mas interpreta os números sob a ótica de negócio, risco e alocação de recursos."""
    dados_reais = _consultar_dados_reais(prompt)
    historico_txt = _formatar_historico(history)

    system_instruction = f"""
    Você é o Assistente Executivo e Estratégico do Predict Ops (Locaweb AIOps).
    Seu papel é apoiar gestores com análise de tendências, previsões D+1 e D+7, risco de SLA/OLA e
    alocação de recursos — sempre traduzindo os dados em impacto de negócio e recomendações.

    Indicadores consolidados, calculados agora a partir do dataset predictops_gold
    (referência de contexto, não são o dado específico da pergunta):
    - Data operacional de referência: {context_kpis.get('data_referencia', '—')}
    - Violação de SLA: {context_kpis.get('taxa_sla', 'indisponível')}
    - Volume médio diário: {context_kpis.get('media_diaria', 'indisponível')}
    - Modelo D+1: {context_kpis.get('previsao_d1', 'indisponível')}
    - Modelo D+7: {context_kpis.get('previsao_d7', 'indisponível')}

    Diretrizes:
    1. Baseie sua resposta nos "Dados reais consultados" informados a seguir, citando os números encontrados.
    2. Se a consulta não retornou dados suficientes ou falhou, diga isso claramente em vez de generalizar.
    3. NUNCA invente números. Se um indicador acima vier como "indisponível", diga que
       está indisponível — não estime, não arredonde e não use valor de exemplo.
    4. Foque em impactos de negócio, riscos operacionais e recomendações acionáveis.
    5. Use o histórico da conversa para manter continuidade entre perguntas.
    6. Mantenha tom executivo, claro e analítico. Não descreva erros técnicos internos
       (SQL, sintaxe, conexão) para o gestor: diga apenas que o dado não pôde ser obtido
       e siga com o que for possível responder.
    """

    prompt_completo = f"""
    Histórico recente da conversa:
    {historico_txt}

    Dados reais consultados na base de incidentes para esta pergunta:
    {dados_reais}

    Pergunta atual do gestor: "{prompt}"
    """
    try:
        return call_gemini(prompt_completo, system_instruction)
    except Exception as err:
        return f"Erro ao consultar o Vertex AI:\n\n{str(err)}"


# ==============================================================================
# LINGUAGEM NATURAL → SQL (NL2SQL)
# ==============================================================================
def natural_language_to_sql(user_prompt: str):
    """Converte pergunta em linguagem natural em SQL SQLite, executa e sintetiza."""
    sql_query, df_res = gerar_e_executar_sql(user_prompt)

    # 4. Geração do resumo explicativo
    summary_prompt = f"""
    O usuário perguntou: "{user_prompt}"
    Consulta SQL executada:
    {sql_query}

    Primeiras linhas do resultado ({len(df_res)} registros encontrados):
    {df_res.head(10).to_string()}

    Escreva um resumo analítico claro em português (máximo 2 parágrafos) sintetizando os principais achados.
    """
    try:
        ai_summary = call_gemini(summary_prompt)
    except Exception:
        ai_summary = "Consulta executada com sucesso e dados recuperados da base de incidentes."

    return sql_query, df_res, ai_summary