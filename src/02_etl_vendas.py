"""Fase 3 - Transformação com Pandas: da camada Raw para a camada Tratada.

Lê os dados brutos exportados do PostgreSQL
(data/raw/vendas_raw_exportadas.csv) e:
    1. Padroniza os nomes das colunas conforme o dicionário de dados;
    2. Remove espaços extras dos textos e marca células vazias como ausentes;
    3. Converte os tipos (decimais, inteiro, data e hora);
    4. Verifica e trata os valores ausentes;
    5. Remove registros duplicados;
    6. Confere os valores calculados (custo, imposto, valor total, receita
       e margem);
    7. Valida as restrições do dicionário (NOT NULL, CHECK e tamanho dos
       textos) e arredonda os decimais para 2 casas;
    8. Cria colunas derivadas de data e hora;
    9. Salva data/processed/vendas_tratadas.csv e carrega a tabela
       vendas_tratadas no PostgreSQL.

Pré-requisito: sql/03_consultas.sql executado (gera o CSV exportado).
Execução (na raiz do projeto): python src/02_etl_vendas.py
"""

import pandas as pd

from banco import consultar, recarregar_tabela
from config import ARQUIVO_CSV_EXPORTADO, ARQUIVO_CSV_TRATADO, RAIZ_PROJETO

# Cabeçalho original -> nome no dicionário de dados da camada Tratada
MAPA_COLUNAS = {
    "Invoice ID": "id_venda",
    "Branch": "filial",
    "City": "cidade",
    "Customer type": "tipo_cliente",
    "Gender": "genero",
    "Product line": "linha_produto",
    "Unit price": "preco_unitario",
    "Quantity": "quantidade",
    "Tax 5%": "imposto",
    "Sales": "valor_total",
    "Date": "data_venda",
    "Time": "hora_venda",
    "Payment": "forma_pagamento",
    "cogs": "custo_mercadoria",
    "gross margin percentage": "margem_percentual",
    "gross income": "receita_bruta",
    "Rating": "avaliacao",
}
COLUNAS_TABELA = list(MAPA_COLUNAS.values())
COLUNAS_DECIMAIS = [
    "preco_unitario", "imposto", "valor_total", "custo_mercadoria",
    "margem_percentual", "receita_bruta", "avaliacao",
]
# NOT NULL do dicionário + preço e quantidade, sem os quais não há venda
COLUNAS_OBRIGATORIAS = [
    "id_venda", "filial", "cidade", "linha_produto", "forma_pagamento",
    "preco_unitario", "quantidade",
]
# Tamanho máximo dos VARCHAR da tabela vendas_tratadas
TAMANHOS_MAXIMOS = {
    "id_venda": 50, "filial": 10, "cidade": 100, "tipo_cliente": 50,
    "genero": 20, "linha_produto": 150, "forma_pagamento": 50,
}
# Restrições CHECK do dicionário (como no SQL, nulo não viola o CHECK)
REGRAS_CHECK = {
    "preco_unitario >= 0": ("preco_unitario", lambda s: s >= 0),
    "quantidade > 0": ("quantidade", lambda s: s > 0),
    "imposto >= 0": ("imposto", lambda s: s >= 0),
    "valor_total >= 0": ("valor_total", lambda s: s >= 0),
    "custo_mercadoria >= 0": ("custo_mercadoria", lambda s: s >= 0),
    "receita_bruta >= 0": ("receita_bruta", lambda s: s >= 0),
    "avaliacao entre 0 e 10": ("avaliacao", lambda s: s.between(0, 10)),
}

ALIQUOTA_IMPOSTO = 0.05
TOLERANCIA = 0.01  # diferença máxima aceita na conferência (1 centavo)

DIAS_SEMANA = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo",
}
MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio",
    6: "Junho", 7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro",
    11: "Novembro", 12: "Dezembro",
}


def etapa(titulo: str) -> None:
    print(f"\n--- {titulo} ---")


def ler_dados_raw() -> pd.DataFrame:
    """Lê o CSV exportado da raw_vendas mantendo os valores como texto."""
    df = pd.read_csv(ARQUIVO_CSV_EXPORTADO, dtype=str, keep_default_na=False)
    caminho = ARQUIVO_CSV_EXPORTADO.relative_to(RAIZ_PROJETO)
    print(f"{len(df)} registros lidos de {caminho}")
    return df


def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia as colunas para o padrão e a ordem do dicionário de dados."""
    faltantes = set(MAPA_COLUNAS) - set(df.columns)
    if faltantes:
        raise ValueError(f"Colunas ausentes no arquivo: {sorted(faltantes)}")
    return df.rename(columns=MAPA_COLUNAS)[COLUNAS_TABELA]


def limpar_textos(df: pd.DataFrame) -> pd.DataFrame:
    """Remove espaços nas pontas e transforma textos vazios em ausentes."""
    df = df.apply(lambda coluna: coluna.str.strip())
    return df.mask(df == "")


def converter_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """Converte os textos para os tipos do dicionário.

    Valores que não podem ser convertidos viram ausentes e são contados
    como falhas de conversão.
    """
    convertido = df.copy()
    for coluna in COLUNAS_DECIMAIS:
        convertido[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    quantidade = pd.to_numeric(df["quantidade"], errors="coerce")
    inteira = quantidade.where(quantidade % 1 == 0)
    convertido["quantidade"] = inteira.astype("Int64")

    convertido["data_venda"] = pd.to_datetime(
        df["data_venda"], format="%m/%d/%Y", errors="coerce"
    )
    convertido["hora_venda"] = pd.to_datetime(
        df["hora_venda"], format="%I:%M:%S %p", errors="coerce"
    ).dt.time

    # Texto preenchido que virou ausente = falha de conversão
    falhas = (df.notna() & convertido.isna()).sum()
    falhas = falhas[falhas > 0].to_dict() or "nenhuma"
    print("Falhas de conversão por coluna:", falhas)
    print(convertido.dtypes.to_string())
    return convertido


def tratar_ausentes(df: pd.DataFrame) -> pd.DataFrame:
    """Verifica os ausentes e remove registros sem os campos obrigatórios.

    - Campos obrigatórios ausentes: o registro é removido, pois não há
      como estimá-los;
    - Campos calculáveis (imposto, valor_total, custo, receita, margem):
      são preenchidos na conferência a partir do preço e da quantidade;
    - Demais campos opcionais (tipo_cliente, genero, data, hora, avaliacao):
      permanecem nulos, pois a tabela os aceita e imputar valores
      distorceria as estatísticas.
    """
    ausentes = df.isna().sum()
    print("Valores ausentes:", ausentes[ausentes > 0].to_dict() or "nenhum")

    sem_obrigatorios = df[COLUNAS_OBRIGATORIAS].isna().any(axis=1)
    print(
        "Registros removidos por falta de campo obrigatório:",
        sem_obrigatorios.sum(),
    )
    return df[~sem_obrigatorios]


def remover_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas idênticas e, depois, repetições da chave id_venda."""
    sem_copias = df.drop_duplicates()
    sem_repetidos = sem_copias.drop_duplicates(subset="id_venda")
    print("Linhas idênticas removidas:", len(df) - len(sem_copias))
    repetidos = len(sem_copias) - len(sem_repetidos)
    print("id_venda repetidos removidos:", repetidos)
    return sem_repetidos


def conferir_calculos(df: pd.DataFrame) -> pd.DataFrame:
    """Recalcula os campos derivados de preço e quantidade e os confere.

    Regras do dataset:
        subtotal          = preço unitário x quantidade
        custo_mercadoria  = subtotal
        imposto           = 5% do subtotal
        valor_total       = subtotal + imposto
        receita_bruta     = valor_total - custo_mercadoria
        margem_percentual = receita_bruta / valor_total x 100
    Valores ausentes ou com diferença acima de 1 centavo são substituídos
    pelo valor calculado.
    """
    df = df.copy()
    subtotal = df["preco_unitario"] * df["quantidade"].astype(float)
    imposto = subtotal * ALIQUOTA_IMPOSTO
    valor_total = subtotal + imposto
    receita = valor_total - subtotal
    esperados = {
        "custo_mercadoria": subtotal,
        "imposto": imposto,
        "valor_total": valor_total,
        "receita_bruta": receita,
        "margem_percentual": receita / valor_total * 100,
    }
    for coluna, esperado in esperados.items():
        divergente = (df[coluna] - esperado).abs() > TOLERANCIA
        corrigir = df[coluna].isna() | divergente
        df.loc[corrigir, coluna] = esperado[corrigir]
        print(
            f"{coluna:<18} conferidos: {len(df) - corrigir.sum():>5} OK"
            f" | recalculados: {corrigir.sum()}"
        )
    return df


def validar_restricoes(df: pd.DataFrame) -> pd.DataFrame:
    """Arredonda os decimais e remove registros que violam as restrições."""
    df = df.copy()
    df[COLUNAS_DECIMAIS] = df[COLUNAS_DECIMAIS].round(2)

    invalidos = pd.Series(False, index=df.index)
    for regra, (coluna, condicao) in REGRAS_CHECK.items():
        violacoes = df[coluna].notna() & ~condicao(df[coluna]).fillna(False)
        print(f"CHECK {regra:<25} violações: {violacoes.sum()}")
        invalidos |= violacoes
    for coluna, tamanho in TAMANHOS_MAXIMOS.items():
        violacoes = (df[coluna].str.len() > tamanho).fillna(False)
        qtd = violacoes.sum()
        print(f"VARCHAR({tamanho:>3}) {coluna:<19} violações: {qtd}")
        invalidos |= violacoes

    print("Registros removidos por violar restrições:", invalidos.sum())
    return df[~invalidos]


def criar_colunas_derivadas(df: pd.DataFrame) -> pd.DataFrame:
    """Cria colunas de calendário e de horário para as análises."""
    df = df.copy()
    dia_da_semana = df["data_venda"].dt.dayofweek  # 0 = segunda-feira
    df["mes"] = df["data_venda"].dt.month.astype("Int64")
    df["nome_mes"] = df["mes"].map(MESES)
    df["num_dia_semana"] = (dia_da_semana + 1).astype("Int64")
    df["dia_semana"] = dia_da_semana.map(DIAS_SEMANA)
    df["hora"] = (
        df["hora_venda"]
        .map(lambda hora: hora.hour, na_action="ignore")
        .astype("Int64")
    )
    df["periodo_dia"] = pd.cut(
        df["hora"],
        bins=[0, 12, 18, 24],
        right=False,
        labels=["Manhã", "Tarde", "Noite"],
    )
    print(
        "Colunas criadas: mes, nome_mes, num_dia_semana, dia_semana, "
        "hora, periodo_dia"
    )
    return df


def salvar_csv(df: pd.DataFrame) -> None:
    ARQUIVO_CSV_TRATADO.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ARQUIVO_CSV_TRATADO, index=False, encoding="utf-8")
    caminho = ARQUIVO_CSV_TRATADO.relative_to(RAIZ_PROJETO)
    print(f"{len(df)} registros salvos em {caminho}")


def carregar_tabela_tratada(df: pd.DataFrame) -> None:
    """Carrega as colunas do dicionário na vendas_tratadas e confere."""
    tabela = df[COLUNAS_TABELA].copy()
    tabela["data_venda"] = tabela["data_venda"].dt.date
    tabela = tabela.astype(object).where(tabela.notna(), None)  # NA -> NULL
    recarregar_tabela(
        "vendas_tratadas",
        COLUNAS_TABELA,
        list(tabela.itertuples(index=False, name=None)),
    )

    _, [(quantidade, soma_banco)] = consultar(
        "SELECT COUNT(*), SUM(valor_total) FROM vendas_tratadas"
    )
    soma_pandas = round(df["valor_total"].sum(), 2)
    if quantidade != len(df) or float(soma_banco) != soma_pandas:
        raise ValueError("A vendas_tratadas não corresponde ao DataFrame.")
    print(
        f"Conferência OK: {quantidade} registros na vendas_tratadas, "
        f"soma do valor_total = {soma_banco}"
    )


def main() -> None:
    etapa("1. Leitura dos dados brutos exportados")
    df = ler_dados_raw()
    total_inicial = len(df)

    etapa("2. Padronização dos nomes das colunas e limpeza dos textos")
    df = limpar_textos(padronizar_colunas(df))
    print("Colunas:", ", ".join(df.columns))

    etapa("3. Conversão de tipos")
    df = converter_tipos(df)

    etapa("4. Valores ausentes")
    df = tratar_ausentes(df)

    etapa("5. Duplicidades")
    df = remover_duplicados(df)

    etapa("6. Conferência dos valores calculados")
    df = conferir_calculos(df)

    etapa("7. Restrições do dicionário de dados e arredondamento")
    df = validar_restricoes(df)

    etapa("8. Colunas derivadas")
    df = criar_colunas_derivadas(df)

    etapa("9. Gravação da camada Tratada")
    salvar_csv(df)
    carregar_tabela_tratada(df)

    print(
        f"\nResumo: {total_inicial} registros lidos -> {len(df)} tratados "
        f"({total_inicial - len(df)} removidos)."
    )


if __name__ == "__main__":
    main()
