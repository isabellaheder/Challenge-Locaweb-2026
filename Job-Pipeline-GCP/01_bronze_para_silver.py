import numpy as np
import pandas as pd

df = pd.read_excel("gs://predictops-bronze/incidentes/LW-DATASET.xlsx")

print(f"Linhas: {df.shape,}")
print(f"Colunas: {df.shape[1]}")

df['tem_resolucao'] = df['Resolvido'].notna().astype(int)
df['Resolvido'] = df['Resolvido'].fillna(df['Encerrado'])
df['tem_pai'] = df['Incidente Pai'].notna().astype(int)
df['tem_produto'] = df['Produto'].notna().astype(int)

df['Produto'] = df.apply(
    lambda row:
        row['Produto']
        if pd.notna(row['Produto'])
        else (
            'MONITORING_AUTO'
            if row['Aberto por'] == 'Monitoramento'
            else 'MANUAL_NAO_CLASSIFICADO'), axis=1)

df['tem_categoria'] = df['Categoria'].notna().astype(int)

def classificar_categoria_inteligente(row):
    if pd.notna(row['Categoria']):
        return row['Categoria']

    if 'MONITORING' in str(row['Produto']):
        return 'INFRA_Monitoramento'

    return 'NAO_CLASSIFICADO_OUTROS'

df['Categoria'] = df.apply(classificar_categoria_inteligente, axis=1)

df['tem_subcategoria'] = (df['Subcategoria'].notna().astype(int))

df['Subcategoria'] = df.apply(
    lambda row:
        row['Subcategoria']
        if pd.notna(row['Subcategoria'])
        else f"{row['Categoria']}_Geral", axis=1)

df['tem_item_config'] = (df['Item de configuração'].notna().astype(int))
df['Item de configuração'] = (df['Item de configuração'].fillna('SEM_IC'))

df['tem_CF'] = (df['Código de fechamento'].notna() & (df['Código de fechamento'] != 'Outro')).astype(int)

def tratar_codigo_fechamento(row):
    codigo = row['Código de fechamento']
    if (
        pd.notna(codigo)
        and codigo.strip().upper() != 'OUTRO'
    ):
        return codigo

    if row['Status'] == 'Sem Intervenção':
        return 'AUTO_SEM_INTERVENCAO'

    if row['Status'] == 'Encerrado Automaticamente':
        return 'AUTO_ENCERRADO'

    return 'NAO_DOCUMENTADO'

df['Código de fechamento'] = df.apply(tratar_codigo_fechamento, axis=1)

def tratar_solucao(row):
    if pd.notna(row['Solução']):
        return row['Solução']

    if row['Status'] == 'Sem Intervenção':
        return 'SEM_SOLUCAO'

    if pd.notna(row['Resolvido']):
        return 'NAO_DOCUMENTADA'

    return 'SEM_SOLUCAO'

df['Solução'] = df.apply(tratar_solucao, axis=1)

def calcular_kpi(row):

    if row['Entrou para KPI?'] == 'NAO':
        return 'NAO_APLICAVEL'

    if pd.notna(row['KPI Violado?']):
        return row['KPI Violado?']

    limites = {
        '1 - Crítica': 4 * 3600,
        '2 - Alta': 4 * 3600,
        '3 - Média': 12 * 3600,
        '4 - Baixa': 24 * 3600,
        '5 - Muito Baixa': 96 * 3600 }

    limite = limites.get(row['Prioridade'], float('inf'))

    return (
        'SIM'
        if row['Duração'] > limite
        else 'NAO'
    )

df['KPI Violado?'] = df.apply(calcular_kpi, axis=1)

df['kpi_violado'] = (df['KPI Violado?'] == 'SIM').astype(int)
df['kpi_nao_aplicavel'] = (df['KPI Violado?'] == 'NAO_APLICAVEL').astype(int)

# salvar camada silver
arquivo_saida = ("gs://predictops-silver/incidentes/"
"incidentes_tratados.parquet")

df.to_parquet(arquivo_saida, index=False)

print("Silver gerada com sucesso!")
print(arquivo_saida)
