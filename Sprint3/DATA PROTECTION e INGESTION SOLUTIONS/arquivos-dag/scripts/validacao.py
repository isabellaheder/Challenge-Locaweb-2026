"""
Validação de qualidade dos dados na camada Silver.
Garante que as regras do dicionário de dados foram cumpridas.
"""
from sqlalchemy import create_engine, text

PG_CONN = 'postgresql+psycopg2://predictops:predictops123@postgres-dw:5432/predictops_dw'


def validar_silver():
    print("Iniciando VALIDAÇÃO da camada Silver...")
    engine = create_engine(PG_CONN)
    erros = []

    with engine.connect() as conn:
        # total de registros
        total = conn.execute(
            text("SELECT COUNT(*) FROM silver.incidentes_tratados")
        ).scalar()
        print(f"Total de registros: {total:,}")
        if total == 0:
            erros.append("Tabela Silver está vazia!")

        # unicidade da pk
        duplicados = conn.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT numero FROM silver.incidentes_tratados
                GROUP BY numero HAVING COUNT(*) > 1
            ) t
        """)).scalar()
        print(f"Keys Duplicidades em 'numero': {duplicados}")
        if duplicados > 0:
            erros.append(f"{duplicados} números duplicados!")

        # nulos em colunas obrigatórias
        colunas_obrigatorias = [
            'prioridade', 'produto', 'categoria', 'subcategoria',
            'grupo_designado', 'item_configuracao', 'aberto',
            'resolvido', 'encerrado', 'duracao', 'codigo_fechamento',
            'descricao_resumida', 'solucao', 'aberto_por', 'status',
            'entrou_kpi', 'kpi_violado_texto'
        ]
        for col in colunas_obrigatorias:
            nulos = conn.execute(text(
                f"SELECT COUNT(*) FROM silver.incidentes_tratados WHERE {col} IS NULL"
            )).scalar()
            if nulos > 0:
                erros.append(f"Coluna '{col}' tem {nulos} nulos!")
            else:
                print(f"{col}: sem nulos")

        # dominio de valores
        # status
        status_invalidos = conn.execute(text("""
            SELECT COUNT(*) FROM silver.incidentes_tratados
            WHERE status NOT IN (
                'Aguardando Problema','Encerrado',
                'Encerrado Automaticamente','Sem Intervenção'
            )
        """)).scalar()
        if status_invalidos > 0:
            erros.append(f"{status_invalidos} status inválidos!")

        # entrou para KPI
        kpi_invalidos = conn.execute(text("""
            SELECT COUNT(*) FROM silver.incidentes_tratados
            WHERE entrou_kpi NOT IN ('SIM','NAO')
        """)).scalar()
        if kpi_invalidos > 0:
            erros.append(f"{kpi_invalidos} entrou_kpi inválidos!")

        # KPI violado
        kpi_v_invalidos = conn.execute(text("""
            SELECT COUNT(*) FROM silver.incidentes_tratados
            WHERE kpi_violado_texto NOT IN ('SIM','NAO','NAO_APLICAVEL')
        """)).scalar()
        if kpi_v_invalidos > 0:
            erros.append(f"{kpi_v_invalidos} kpi_violado_texto inválidos!")

        # prioridade
        prio_invalidas = conn.execute(text("""
            SELECT COUNT(*) FROM silver.incidentes_tratados
            WHERE prioridade NOT IN (
                '1 - Crítica','2 - Alta','3 - Média',
                '4 - Baixa','5 - Muito Baixa'
            )
        """)).scalar()
        if prio_invalidas > 0:
            erros.append(f"{prio_invalidas} prioridades inválidas!")

        # flags binárias 
        flags = ['tem_resolucao','tem_pai','tem_produto','tem_categoria',
                 'tem_subcategoria','tem_item_config','tem_cf',
                 'kpi_violado','kpi_nao_aplicavel']
        for flag in flags:
            invalidos = conn.execute(text(
                f"SELECT COUNT(*) FROM silver.incidentes_tratados WHERE {flag} NOT IN (0,1)"
            )).scalar()
            if invalidos > 0:
                erros.append(f"Flag '{flag}' tem {invalidos} valores inválidos!")

        # coerencia de datas
        datas_inv = conn.execute(text("""
            SELECT COUNT(*) FROM silver.incidentes_tratados
            WHERE encerrado < aberto
        """)).scalar()
        if datas_inv > 0:
            erros.append(f"{datas_inv} registros com encerrado < aberto!")

    # resultado
    if erros:
        print("\nERROS DE VALIDAÇÃO:")
        for e in erros:
            print(f"  - {e}")
        raise ValueError(f"Validação falhou com {len(erros)} erro(s)")
    else:
        print("\nVALIDAÇÃO OK - Todos os critérios atendidos!")

    return total

if __name__ == '__main__':
    validar_silver()