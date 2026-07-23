"""
Camada SILVER (Staging Zone)
Aplica TODAS as regras de tratamento de nulos e cria flags
conforme dicionário de dados.
"""
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

PG_CONN = 'postgresql+psycopg2://predictops:predictops123@postgres-dw:5432/predictops_dw'


def transform_silver():
    print("🥈 Iniciando transformação SILVER...")

    engine = create_engine(PG_CONN)
    df = pd.read_sql('SELECT * FROM bronze.incidentes_raw', engine)
    print(f"📊 Registros lidos da Bronze: {len(df):,}")

    # ============================================================
    # 1. CONVERSÃO DE DATAS
    # ============================================================
    for col in ['aberto', 'resolvido', 'encerrado']:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    # ============================================================
    # 2. FLAG tem_resolucao + preenchimento
    # ============================================================
    df['tem_resolucao'] = df['resolvido'].notna().astype(int)
    df['resolvido'] = df['resolvido'].fillna(df['encerrado'])

    # ============================================================
    # 3. FLAG tem_pai
    # ============================================================
    df['tem_pai'] = df['incidente_pai'].notna().astype(int)

    # ============================================================
    # 4. FLAG tem_produto + tratamento
    # ============================================================
    df['tem_produto'] = df['produto'].notna().astype(int)
    df['produto'] = df.apply(
        lambda r: r['produto'] if pd.notna(r['produto'])
        else 'MONITORING_AUTO' if r['aberto_por'] == 'Monitoramento'
        else 'MANUAL_NAO_CLASSIFICADO',
        axis=1
    )

    # ============================================================
    # 5. FLAG tem_categoria + classificação inteligente
    # ============================================================
    df['tem_categoria'] = df['categoria'].notna().astype(int)

    def classificar_categoria(r):
        if pd.notna(r['categoria']):
            return r['categoria']
        if 'MONITORING' in str(r['produto']):
            return 'INFRA_Monitoramento'
        return 'NAO_CLASSIFICADO_OUTROS'

    df['categoria'] = df.apply(classificar_categoria, axis=1)

    # ============================================================
    # 6. FLAG tem_subcategoria + preenchimento
    # ============================================================
    df['tem_subcategoria'] = df['subcategoria'].notna().astype(int)
    df['subcategoria'] = df.apply(
        lambda r: r['subcategoria'] if pd.notna(r['subcategoria'])
        else f"{r['categoria']}_Geral",
        axis=1
    )

    # ============================================================
    # 7. FLAG tem_item_config + preenchimento
    # ============================================================
    df['tem_item_config'] = df['item_configuracao'].notna().astype(int)
    df['item_configuracao'] = df['item_configuracao'].fillna('SEM_IC')

    # ============================================================
    # 8. FLAG tem_cf + tratamento Código de Fechamento
    # ============================================================
    df['tem_cf'] = (
        df['codigo_fechamento'].notna() &
        (df['codigo_fechamento'] != 'Outro')
    ).astype(int)

    def tratar_codigo_fechamento(r):
        codigo = r['codigo_fechamento']
        if pd.notna(codigo) and str(codigo).strip().upper() != 'OUTRO':
            return codigo
        if r['status'] == 'Sem Intervenção':
            return 'AUTO_SEM_INTERVENCAO'
        elif r['status'] == 'Encerrado Automaticamente':
            return 'AUTO_ENCERRADO'
        return 'NAO_DOCUMENTADO'

    df['codigo_fechamento'] = df.apply(tratar_codigo_fechamento, axis=1)

    # ============================================================
    # 9. TRATAMENTO DE SOLUÇÃO
    # ============================================================
    def tratar_solucao(r):
        if pd.notna(r['solucao']):
            return r['solucao']
        if r['status'] == 'Sem Intervenção':
            return 'SEM_SOLUCAO'
        if pd.notna(r['resolvido']):
            return 'NAO_DOCUMENTADA'
        return 'SEM_SOLUCAO'

    df['solucao'] = df.apply(tratar_solucao, axis=1)

    # ============================================================
    # 10. CÁLCULO KPI VIOLADO
    # ============================================================
    def calcular_kpi(r):
        if r['entrou_kpi'] == 'NAO':
            return 'NAO_APLICAVEL'
        if pd.notna(r['kpi_violado']):
            return r['kpi_violado']
        limites = {
            '1 - Crítica':     4 * 3600,
            '2 - Alta':        4 * 3600,
            '3 - Média':      12 * 3600,
            '4 - Baixa':      24 * 3600,
            '5 - Muito Baixa': 96 * 3600,
        }
        limite = limites.get(r['prioridade'], float('inf'))
        return 'SIM' if r['duracao'] > limite else 'NAO'

    df['kpi_violado_texto'] = df.apply(calcular_kpi, axis=1)
    df['kpi_violado'] = np.where(df['kpi_violado_texto'] == 'SIM', 1, 0)
    df['kpi_nao_aplicavel'] = (df['kpi_violado_texto'] == 'NAO_APLICAVEL').astype(int)

    # ============================================================
    # 11. SELEÇÃO FINAL DE COLUNAS
    # ============================================================
    df_final = df[[
        'numero', 'prioridade', 'produto', 'categoria', 'subcategoria',
        'grupo_designado', 'item_configuracao', 'aberto', 'resolvido',
        'encerrado', 'duracao', 'codigo_fechamento', 'descricao_resumida',
        'solucao', 'aberto_por', 'incidente_pai', 'status', 'entrou_kpi',
        'kpi_violado_texto',
        'tem_resolucao', 'tem_pai', 'tem_produto', 'tem_categoria',
        'tem_subcategoria', 'tem_item_config', 'tem_cf',
        'kpi_violado', 'kpi_nao_aplicavel'
    ]].copy()

    print(f"📊 Após transformação: {df_final.shape}")
    print(f"📋 Nulos remanescentes:\n{df_final.isnull().sum()}")

    # ============================================================
    # 12. CARGA NA SILVER
    # ============================================================
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE silver.incidentes_tratados"))
        print("🧹 silver.incidentes_tratados truncada")

    df_final.to_sql(
        'incidentes_tratados',
        engine,
        schema='silver',
        if_exists='append',
        index=False,
        chunksize=5000,
        method='multi'
    )

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM silver.incidentes_tratados")).scalar()

    print(f"✅ SILVER carregada: {total:,} registros em silver.incidentes_tratados")
    return total


if __name__ == '__main__':
    transform_silver()