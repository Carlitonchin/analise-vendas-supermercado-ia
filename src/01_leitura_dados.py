"""Fase 1 - Extração, leitura e inspeção do CSV e carga da camada Raw.

Etapas:
    1. Garante que o CSV original esteja em data/raw/ (baixa da fonte
       pública se o arquivo não existir);
    2. Lê o CSV no Pandas e faz a inspeção inicial (estrutura, tipos,
       ausentes, duplicidades, categorias e formatos de data/hora);
    3. Carrega os dados brutos, sem alterar o conteúdo, na tabela raw_vendas;
    4. Lê a tabela de volta e confere se o conteúdo é idêntico ao arquivo.

Pré-requisito: sql/01_criar_banco.sql e sql/02_criar_tabelas.sql executados.
Execução (na raiz do projeto): python src/01_leitura_dados.py
"""

import urllib.request

import pandas as pd

from banco import consultar, recarregar_tabela
from config import (
    ARQUIVO_CSV_ORIGINAL,
    COLUNAS_RAW,
    DIR_RESULTADOS,
    RAIZ_PROJETO,
    URL_DATASET,
)

ARQUIVO_RELATORIO = DIR_RESULTADOS / "01_inspecao_inicial.txt"

COLUNAS_CATEGORICAS = [
    "Branch", "City", "Customer type", "Gender", "Product line", "Payment",
]
COLUNAS_NUMERICAS = [
    "Unit price", "Quantity", "Tax 5%", "Sales", "cogs",
    "gross margin percentage", "gross income", "Rating",
]
ROTULOS_RESUMO = {
    "count": "contagem", "mean": "media", "std": "desvio_padrao",
    "min": "minimo", "25%": "q1_25%", "50%": "mediana", "75%": "q3_75%",
    "max": "maximo",
}
PADRAO_DATA = r"^\d{1,2}/\d{1,2}/\d{4}$"  # M/D/AAAA
PADRAO_HORA = r"^\d{1,2}:\d{2}:\d{2} (?:AM|PM)$"  # H:MM:SS AM/PM


def garantir_csv_original() -> None:
    """Baixa o dataset da fonte pública caso ele não esteja em data/raw/."""
    caminho = ARQUIVO_CSV_ORIGINAL.relative_to(RAIZ_PROJETO)
    if ARQUIVO_CSV_ORIGINAL.exists():
        print(f"CSV original encontrado em {caminho}")
        return
    print(f"CSV original não encontrado. Baixando para {caminho} ...")
    ARQUIVO_CSV_ORIGINAL.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(URL_DATASET, ARQUIVO_CSV_ORIGINAL)


def ler_csv_como_texto() -> pd.DataFrame:
    """Lê todas as colunas como texto, exatamente como estão no arquivo.

    keep_default_na=False impede que o Pandas troque células vazias por NaN,
    e utf-8-sig descarta o BOM do início do arquivo (não faz parte dos dados).
    """
    df = pd.read_csv(
        ARQUIVO_CSV_ORIGINAL,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    if list(df.columns) != list(COLUNAS_RAW):
        raise ValueError(f"Cabeçalho inesperado no CSV: {list(df.columns)}")
    return df


def casas_decimais(serie: pd.Series) -> int:
    """Maior quantidade de casas decimais de uma coluna numérica em texto."""
    return int(serie.str.partition(".")[2].str.len().max())


def inspecionar(df_texto: pd.DataFrame) -> str:
    """Monta o relatório de inspeção inicial do CSV."""
    # Segunda leitura, deixando o Pandas inferir os tipos de cada coluna
    df = pd.read_csv(ARQUIVO_CSV_ORIGINAL, encoding="utf-8-sig")
    total = len(df)
    secoes = []

    def secao(titulo: str, conteudo: str) -> None:
        secoes.append(f"{'=' * 78}\n{titulo}\n{'=' * 78}\n{conteudo}\n")

    secao("1. Dimensões", f"{total} linhas x {df.shape[1]} colunas")
    secao("2. Primeiras 5 linhas (transpostas)", df.head().T.to_string())
    secao(
        "3. Tipos inferidos pelo Pandas "
        "(str = texto, int64 = inteiro, float64 = decimal)",
        df.dtypes.to_string(),
    )
    secao("4. Valores ausentes por coluna", df.isna().sum().to_string())
    secao(
        "5. Duplicidades",
        f"Linhas completamente duplicadas: {df.duplicated().sum()}\n"
        f"Invoice ID repetidos: {df['Invoice ID'].duplicated().sum()}",
    )
    secao(
        "6. Valores distintos das colunas categóricas",
        "\n\n".join(
            df[coluna].value_counts().to_string()
            for coluna in COLUNAS_CATEGORICAS
        ),
    )
    resumo = df[COLUNAS_NUMERICAS].describe().T.rename(columns=ROTULOS_RESUMO)
    secao("7. Resumo das colunas numéricas", resumo.to_string())

    datas_validas = df_texto["Date"].str.match(PADRAO_DATA).sum()
    horas_validas = df_texto["Time"].str.match(PADRAO_HORA).sum()
    datas = pd.to_datetime(
        df_texto["Date"], format="%m/%d/%Y", errors="coerce"
    )
    secao(
        "8. Formatos de data e hora (armazenadas como texto)",
        f"Exemplos de Date: {df_texto['Date'].head(3).tolist()}\n"
        f"Exemplos de Time: {df_texto['Time'].head(3).tolist()}\n"
        f"Datas no padrão M/D/AAAA: {datas_validas} de {total}\n"
        f"Horas no padrão H:MM:SS AM/PM: {horas_validas} de {total}\n"
        f"Período: {datas.min():%d/%m/%Y} a {datas.max():%d/%m/%Y}",
    )

    decimais = "\n".join(
        f"    {coluna:<25} {casas_decimais(df_texto[coluna])}"
        for coluna in COLUNAS_NUMERICAS
    )
    margens = df["gross margin percentage"].nunique()
    secao(
        "9. Pontos de atenção para o ETL",
        "- Nomes de colunas em inglês, com espaços e símbolos "
        "(ex.: 'Tax 5%'): padronizar para snake_case em português.\n"
        f"- Date e Time foram lidas como '{df['Date'].dtype}': "
        "converter para DATE e TIME.\n"
        "- Máximo de casas decimais por coluna numérica "
        "(o destino usa NUMERIC(x,2)):\n"
        f"{decimais}\n"
        f"- 'gross margin percentage' tem {margens} valor(es) distinto(s).",
    )
    return "\n".join(secoes)


def carregar_raw(df_texto: pd.DataFrame) -> None:
    """Grava os registros na raw_vendas como lidos, com arquivo e linha."""
    colunas = list(COLUNAS_RAW.values()) + ["arquivo_origem", "linha_arquivo"]
    nome_arquivo = ARQUIVO_CSV_ORIGINAL.name
    # A linha 1 do arquivo é o cabeçalho: o 1º registro está na linha 2.
    linhas = [
        (*registro, nome_arquivo, numero_linha)
        for numero_linha, registro in enumerate(
            df_texto.itertuples(index=False, name=None), start=2
        )
    ]
    recarregar_tabela("raw_vendas", colunas, linhas)
    print(f"{len(linhas)} registros carregados na tabela raw_vendas.")


def conferir_carga(df_texto: pd.DataFrame) -> None:
    """Compara o conteúdo da raw_vendas com o CSV original, célula a célula."""
    _, linhas = consultar(
        f"SELECT {', '.join(COLUNAS_RAW.values())} "
        "FROM raw_vendas ORDER BY linha_arquivo"
    )
    df_banco = pd.DataFrame(linhas, columns=list(COLUNAS_RAW), dtype="str")
    if not df_banco.equals(df_texto):
        raise ValueError("O conteúdo da raw_vendas difere do CSV original.")
    print(
        f"Conferência OK: {len(df_banco)} registros da raw_vendas "
        f"idênticos ao arquivo {ARQUIVO_CSV_ORIGINAL.name}."
    )


def main() -> None:
    garantir_csv_original()
    df_texto = ler_csv_como_texto()

    relatorio = inspecionar(df_texto)
    print(relatorio)
    ARQUIVO_RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_RELATORIO.write_text(relatorio, encoding="utf-8")
    print(f"Relatório salvo em {ARQUIVO_RELATORIO.relative_to(RAIZ_PROJETO)}")

    carregar_raw(df_texto)
    conferir_carga(df_texto)


if __name__ == "__main__":
    main()
