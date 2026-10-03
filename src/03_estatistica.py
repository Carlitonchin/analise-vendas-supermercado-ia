"""Fase 4 - Análise e camada Gold: estatística, respostas e gráficos.

Lê a camada Tratada (data/processed/vendas_tratadas.csv) e gera em
resultados/:
    - estatisticas_descritivas.csv: medidas de posição e dispersão;
    - tabelas/*.csv: agregações que sustentam cada resposta;
    - respostas_negocio.csv e .md: respostas às 8 perguntas de negócio;
    - graficos/*.png: um gráfico para cada pergunta.

Execução (na raiz do projeto): python src/03_estatistica.py
"""

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

from config import (
    ARQUIVO_CSV_TRATADO,
    DIR_GRAFICOS,
    DIR_RESULTADOS,
    DIR_TABELAS,
    RAIZ_PROJETO,
)

COLUNAS_NUMERICAS = [
    "preco_unitario", "quantidade", "imposto", "valor_total",
    "custo_mercadoria", "margem_percentual", "receita_bruta", "avaliacao",
]
COLUNAS_CATEGORICAS = [
    "filial", "cidade", "tipo_cliente", "genero", "linha_produto",
    "forma_pagamento", "dia_semana", "periodo_dia",
]
# Os dados mantêm os valores originais do dataset (em inglês); nos
# resultados (tabelas, respostas e gráficos) as categorias são traduzidas.
TRADUCOES = {
    "linha_produto": {
        "Electronic accessories": "Acessórios eletrônicos",
        "Fashion accessories": "Acessórios de moda",
        "Food and beverages": "Alimentos e bebidas",
        "Health and beauty": "Saúde e beleza",
        "Home and lifestyle": "Casa e estilo de vida",
        "Sports and travel": "Esportes e viagens",
    },
    "forma_pagamento": {
        "Cash": "Dinheiro",
        "Credit card": "Cartão de crédito",
        "Ewallet": "Carteira digital",
    },
    "tipo_cliente": {"Member": "Membro", "Normal": "Normal"},
    "genero": {"Female": "Feminino", "Male": "Masculino"},
}
COLUNAS_MAIOR_VENDA = [
    "filial", "cidade", "linha_produto", "preco_unitario", "quantidade",
    "imposto", "valor_total", "data_venda", "hora_venda", "forma_pagamento",
]

# Paleta dos gráficos: azul destaca a resposta, cinza neutro é o contexto
COR_DESTAQUE = "#2a78d6"
COR_CONTEXTO = "#b4b3ab"
COR_TEXTO = "#0b0b0b"
COR_TEXTO_SECUNDARIO = "#52514e"
COR_GRADE = "#e4e3de"
COR_FUNDO = "#fcfcfb"


# ------------------------------------------------------------------------
# Utilitários
# ------------------------------------------------------------------------
def formatar_numero(valor: float, casas: int = 2) -> str:
    """Formata um número no padrão brasileiro (1.234,56)."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def lideres(serie: pd.Series) -> list[str]:
    """Categorias com o maior valor (mais de uma em caso de empate)."""
    return serie[serie == serie.max()].index.tolist()


def comparar_com_segundo(serie: pd.Series, casas: int = 2) -> str:
    """Descreve a vantagem do primeiro colocado sobre o segundo."""
    ordenada = serie.sort_values(ascending=False)
    primeiro, segundo = ordenada.iloc[0], ordenada.iloc[1]
    diferenca = primeiro - segundo
    percentual = diferenca / segundo * 100
    return (
        f"2º lugar: {ordenada.index[1]} ({formatar_numero(segundo, casas)}); "
        f"diferença de {formatar_numero(diferenca, casas)} "
        f"({formatar_numero(percentual, 1)}%)"
    )


def traduzir_categorias(df: pd.DataFrame) -> pd.DataFrame:
    """Troca os valores das categorias pelos nomes em português.

    Valores sem tradução cadastrada são mantidos como estão.
    """
    df = df.copy()
    for coluna, traducao in TRADUCOES.items():
        df[coluna] = df[coluna].replace(traducao)
    return df


def nome_filial(df: pd.DataFrame, filial: str) -> str:
    """Nome da filial acompanhado da cidade, ex.: 'Giza (Naypyitaw)'."""
    cidade = df.loc[df["filial"] == filial, "cidade"].iloc[0]
    return f"{filial} ({cidade})"


def salvar_tabela(tabela: pd.DataFrame, nome: str) -> None:
    tabela.to_csv(DIR_TABELAS / f"{nome}.csv", encoding="utf-8")


def tabela_markdown(tabela: pd.DataFrame) -> str:
    """Converte um DataFrame simples em tabela Markdown."""
    linhas = [
        "| " + " | ".join(tabela.columns) + " |",
        "|" + "---|" * len(tabela.columns),
    ]
    for linha in tabela.itertuples(index=False):
        linhas.append("| " + " | ".join(map(str, linha)) + " |")
    return "\n".join(linhas)


# ------------------------------------------------------------------------
# Gráficos
# ------------------------------------------------------------------------
def configurar_estilo() -> None:
    plt.rcParams.update({
        "figure.facecolor": COR_FUNDO,
        "axes.facecolor": COR_FUNDO,
        "axes.edgecolor": COR_TEXTO_SECUNDARIO,
        "axes.labelcolor": COR_TEXTO_SECUNDARIO,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": COR_TEXTO_SECUNDARIO,
        "ytick.color": COR_TEXTO_SECUNDARIO,
        "font.size": 10,
        "savefig.dpi": 150,
        "savefig.facecolor": COR_FUNDO,
    })


def novo_grafico(titulo: str, subtitulo: str):
    """Cria a figura com título (a resposta) e subtítulo (a métrica)."""
    fig, ax = plt.subplots(figsize=(8.5, 5))
    fig.text(0.02, 0.96, titulo, ha="left", va="top", fontsize=14,
             fontweight="bold", color=COR_TEXTO)
    fig.text(0.02, 0.89, subtitulo, ha="left", va="top", fontsize=10,
             color=COR_TEXTO_SECUNDARIO)
    return fig, ax


def finalizar_grafico(fig, nome_arquivo: str) -> None:
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    fig.savefig(DIR_GRAFICOS / nome_arquivo)
    plt.close(fig)
    print(f"  gráfico salvo: resultados/graficos/{nome_arquivo}")


def grafico_barras(serie: pd.Series, titulo: str, subtitulo: str,
                   nome_arquivo: str, rotulos: list[str],
                   horizontal: bool = False,
                   limite: tuple[float, float] | None = None) -> None:
    """Barras de uma única série, com a(s) líder(es) destacada(s) em azul."""
    destaques = lideres(serie)
    cores = [
        COR_DESTAQUE if categoria in destaques else COR_CONTEXTO
        for categoria in serie.index
    ]
    categorias = [str(categoria) for categoria in serie.index]
    fig, ax = novo_grafico(titulo, subtitulo)
    formatador = FuncFormatter(lambda valor, _: formatar_numero(valor, 0))

    if horizontal:
        barras = ax.barh(categorias, serie.values, color=cores, height=0.6)
        ax.invert_yaxis()  # primeira categoria no topo
        eixo_valores, eixo_categorias, base = ax.xaxis, "y", "bottom"
        ax.margins(x=0.08)
        if limite:
            ax.set_xlim(*limite)
    else:
        barras = ax.bar(categorias, serie.values, color=cores, width=0.6)
        eixo_valores, eixo_categorias, base = ax.yaxis, "x", "left"
        ax.margins(y=0.12)
        if limite:
            ax.set_ylim(*limite)

    eixo_valores.set_major_formatter(formatador)
    eixo_valores.grid(True, color=COR_GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[base].set_visible(False)
    ax.tick_params(length=0)
    ax.tick_params(axis=eixo_categorias, labelcolor=COR_TEXTO)
    ax.bar_label(barras, labels=rotulos, padding=4, color=COR_TEXTO,
                 fontsize=9)
    finalizar_grafico(fig, nome_arquivo)


def grafico_distribuicao_vendas(valores: pd.Series, titulo: str,
                                nome_arquivo: str) -> None:
    """Histograma do valor das vendas com média, mediana e maior venda."""
    media, mediana, maximo = valores.mean(), valores.median(), valores.max()
    fig, ax = novo_grafico(
        titulo, "Distribuição do valor total por venda (faixas de 50)"
    )
    ax.hist(valores, bins=range(0, 1101, 50), color=COR_CONTEXTO,
            edgecolor=COR_FUNDO, linewidth=2)
    ax.yaxis.grid(True, color=COR_GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Valor da venda")
    ax.set_ylabel("Quantidade de vendas")
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda valor, _: formatar_numero(valor, 0))
    )

    topo = ax.get_ylim()[1]
    marcas = [
        (media, COR_DESTAQUE, "Média", "left", 12),
        (mediana, COR_TEXTO_SECUNDARIO, "Mediana", "right", -12),
    ]
    for posicao, cor, nome, alinhamento, deslocamento in marcas:
        ax.axvline(posicao, color=cor, linewidth=2)
        ax.annotate(f"{nome}\n{formatar_numero(posicao)}",
                    xy=(posicao, topo * 0.97), xytext=(deslocamento, 0),
                    textcoords="offset points", ha=alinhamento, va="top",
                    color=COR_TEXTO, fontsize=9)
    ax.annotate(f"Maior venda\n{formatar_numero(maximo)}",
                xy=(maximo, 1), xytext=(maximo, topo * 0.45), ha="center",
                color=COR_TEXTO, fontsize=9,
                arrowprops={"arrowstyle": "->",
                            "color": COR_TEXTO_SECUNDARIO})
    finalizar_grafico(fig, nome_arquivo)


# ------------------------------------------------------------------------
# Estatística descritiva
# ------------------------------------------------------------------------
def estatistica_descritiva(df: pd.DataFrame) -> None:
    """Medidas de posição e dispersão de cada coluna numérica."""
    numericas = df[COLUNAS_NUMERICAS].astype(float)
    resumo = pd.DataFrame({
        "contagem": numericas.count(),
        "media": numericas.mean(),
        "mediana": numericas.median(),
        "moda": numericas.mode().iloc[0],  # a menor, se houver várias
        "desvio_padrao": numericas.std(),
        "variancia": numericas.var(),
        "minimo": numericas.min(),
        "q1_25%": numericas.quantile(0.25),
        "q3_75%": numericas.quantile(0.75),
        "maximo": numericas.max(),
        "amplitude": numericas.max() - numericas.min(),
        "coef_variacao_%": numericas.std() / numericas.mean() * 100,
        "assimetria": numericas.skew(),
    }).round(2)
    resumo.index.name = "coluna"
    resumo.to_csv(DIR_RESULTADOS / "estatisticas_descritivas.csv",
                  encoding="utf-8")
    print(resumo.to_string())


def frequencias_categoricas(df: pd.DataFrame) -> None:
    """Contagem e percentual de cada categoria das colunas qualitativas."""
    tabelas = []
    for coluna in COLUNAS_CATEGORICAS:
        contagem = df[coluna].value_counts()
        tabelas.append(pd.DataFrame({
            "coluna": coluna,
            "categoria": contagem.index.astype(str),
            "quantidade": contagem.values,
            "percentual": (contagem.values / len(df) * 100).round(1),
        }))
    pd.concat(tabelas).to_csv(DIR_TABELAS / "frequencias_categoricas.csv",
                              index=False, encoding="utf-8")


# ------------------------------------------------------------------------
# Perguntas de negócio
# ------------------------------------------------------------------------
def p1_filial_maior_faturamento(df: pd.DataFrame) -> dict:
    faturamento = df.groupby("filial")["valor_total"].sum()
    faturamento = faturamento.sort_values(ascending=False)
    salvar_tabela(faturamento.round(2).to_frame("faturamento"),
                  "p1_faturamento_por_filial")
    vencedoras = ", ".join(
        nome_filial(df, filial) for filial in lideres(faturamento)
    )
    grafico_barras(
        faturamento.rename(index=lambda filial: nome_filial(df, filial)),
        f"{vencedoras} teve o maior faturamento",
        "Faturamento total por filial (soma do valor total das vendas)",
        "p1_faturamento_por_filial.png",
        rotulos=[formatar_numero(valor) for valor in faturamento],
    )
    return {
        "pergunta": "Qual filial apresentou o maior faturamento?",
        "resposta": vencedoras,
        "metrica": f"Faturamento de {formatar_numero(faturamento.max())}",
        "observacao": comparar_com_segundo(faturamento),
    }


def p2_filial_mais_vendas(df: pd.DataFrame) -> dict:
    vendas = df.groupby("filial").agg(
        quantidade_vendas=("id_venda", "count"),
        unidades_vendidas=("quantidade", "sum"),
    ).sort_values("quantidade_vendas", ascending=False)
    salvar_tabela(vendas, "p2_vendas_por_filial")
    quantidade = vendas["quantidade_vendas"]
    vencedoras = ", ".join(
        nome_filial(df, filial) for filial in lideres(quantidade)
    )
    grafico_barras(
        quantidade.rename(index=lambda filial: nome_filial(df, filial)),
        f"{vencedoras} realizou mais vendas",
        "Quantidade de vendas (notas fiscais) por filial",
        "p2_vendas_por_filial.png",
        rotulos=[str(valor) for valor in quantidade],
    )
    unidades = vendas["unidades_vendidas"].iloc[0]
    return {
        "pergunta": "Qual filial realizou a maior quantidade de vendas?",
        "resposta": vencedoras,
        "metrica": f"{quantidade.max()} vendas ({unidades} unidades)",
        "observacao": comparar_com_segundo(quantidade, casas=0),
    }


def p3_linha_maior_faturamento(df: pd.DataFrame) -> dict:
    faturamento = df.groupby("linha_produto")["valor_total"].sum()
    faturamento = faturamento.sort_values(ascending=False)
    salvar_tabela(faturamento.round(2).to_frame("faturamento"),
                  "p3_faturamento_por_linha_produto")
    vencedoras = ", ".join(lideres(faturamento))
    grafico_barras(
        faturamento,
        f"{vencedoras} lidera o faturamento",
        "Faturamento total por linha de produto",
        "p3_faturamento_por_linha_produto.png",
        rotulos=[formatar_numero(valor) for valor in faturamento],
        horizontal=True,
    )
    return {
        "pergunta": "Qual linha de produto apresentou o maior faturamento?",
        "resposta": vencedoras,
        "metrica": f"Faturamento de {formatar_numero(faturamento.max())}",
        "observacao": comparar_com_segundo(faturamento),
    }


def p4_linha_melhor_avaliacao(df: pd.DataFrame) -> dict:
    avaliacao = df.groupby("linha_produto")["avaliacao"].mean().round(2)
    avaliacao = avaliacao.sort_values(ascending=False)
    salvar_tabela(avaliacao.to_frame("avaliacao_media"),
                  "p4_avaliacao_media_por_linha_produto")
    vencedoras = ", ".join(lideres(avaliacao))
    grafico_barras(
        avaliacao,
        f"{vencedoras} tem a melhor avaliação média",
        "Avaliação média dos clientes por linha de produto (escala 0 a 10)",
        "p4_avaliacao_media_por_linha_produto.png",
        rotulos=[formatar_numero(valor) for valor in avaliacao],
        horizontal=True,
        limite=(0, 10),
    )
    return {
        "pergunta": "Qual linha de produto recebeu a melhor avaliação média?",
        "resposta": vencedoras,
        "metrica": f"Avaliação média de {formatar_numero(avaliacao.max())}",
        "observacao": comparar_com_segundo(avaliacao),
    }


def p5_forma_pagamento(df: pd.DataFrame) -> dict:
    pagamentos = df["forma_pagamento"].value_counts()
    percentual = pagamentos / pagamentos.sum() * 100
    salvar_tabela(
        pd.DataFrame({"quantidade_vendas": pagamentos,
                      "percentual": percentual.round(1)}),
        "p5_formas_pagamento",
    )
    vencedoras = ", ".join(lideres(pagamentos))
    grafico_barras(
        pagamentos,
        f"{vencedoras} foi a forma de pagamento mais usada",
        "Quantidade de vendas por forma de pagamento",
        "p5_formas_pagamento.png",
        rotulos=[
            f"{valor} ({formatar_numero(pct, 1)}%)"
            for valor, pct in zip(pagamentos, percentual, strict=True)
        ],
    )
    return {
        "pergunta": "Qual foi a forma de pagamento mais utilizada?",
        "resposta": vencedoras,
        "metrica": f"{pagamentos.max()} vendas "
                   f"({formatar_numero(percentual.max(), 1)}% do total)",
        "observacao": comparar_com_segundo(pagamentos, casas=0),
    }


def p6_p7_valor_vendas(df: pd.DataFrame) -> list[dict]:
    valores = df["valor_total"]
    media, mediana, maximo = valores.mean(), valores.median(), valores.max()
    maior = df.loc[valores == maximo]
    salvar_tabela(maior.set_index("id_venda")[COLUNAS_MAIOR_VENDA],
                  "p7_maior_venda")
    grafico_distribuicao_vendas(
        valores,
        f"Venda média de {formatar_numero(media)}; "
        f"maior venda de {formatar_numero(maximo)}",
        "p6_p7_distribuicao_valor_vendas.png",
    )

    if media > mediana:
        leitura = ("distribuição assimétrica à direita: poucas vendas "
                   "grandes puxam a média para cima")
    else:
        leitura = "média não está acima da mediana"
    venda = maior.iloc[0]
    return [
        {
            "pergunta": "Qual foi o valor médio das vendas?",
            "resposta": formatar_numero(media),
            "metrica": f"Média de {len(valores)} vendas",
            "observacao": f"Mediana de {formatar_numero(mediana)} e desvio "
                          f"padrão de {formatar_numero(valores.std())}; "
                          f"{leitura}",
        },
        {
            "pergunta": "Qual foi a maior venda registrada?",
            "resposta": formatar_numero(maximo),
            "metrica": f"Venda {', '.join(maior['id_venda'])}",
            "observacao": f"{venda['quantidade']} x {venda['linha_produto']}"
                          f" a {formatar_numero(venda['preco_unitario'])} "
                          f"na filial {nome_filial(df, venda['filial'])}, "
                          f"em {venda['data_venda']:%d/%m/%Y}, paga com "
                          f"{venda['forma_pagamento'].lower()}",
        },
    ]


def p8_dia_semana(df: pd.DataFrame) -> dict:
    # Agrupar também pelo número do dia mantém a ordem segunda -> domingo
    vendas = df.groupby(["num_dia_semana", "dia_semana"]).size()
    vendas = vendas.droplevel("num_dia_semana")
    salvar_tabela(vendas.to_frame("quantidade_vendas"),
                  "p8_vendas_por_dia_semana")
    vencedores = ", ".join(lideres(vendas))
    grafico_barras(
        vendas,
        f"{vencedores} é o dia com mais vendas",
        "Quantidade de vendas por dia da semana",
        "p8_vendas_por_dia_semana.png",
        rotulos=[str(valor) for valor in vendas],
    )
    return {
        "pergunta": "Em qual dia da semana ocorreu a maior quantidade "
                    "de vendas?",
        "resposta": vencedores,
        "metrica": f"{vendas.max()} vendas",
        "observacao": comparar_com_segundo(vendas, casas=0),
    }


def salvar_respostas(respostas: list[dict]) -> None:
    tabela = pd.DataFrame(respostas)
    tabela.insert(0, "numero", range(1, len(tabela) + 1))
    tabela.to_csv(DIR_RESULTADOS / "respostas_negocio.csv", index=False,
                  encoding="utf-8")

    titulos = {"numero": "#", "pergunta": "Pergunta",
               "resposta": "Resposta", "metrica": "Métrica",
               "observacao": "Observação"}
    markdown = [
        "# Respostas às perguntas de negócio",
        "",
        "Gerado automaticamente por `src/03_estatistica.py` a partir de "
        "`data/processed/vendas_tratadas.csv`.",
        "",
        tabela_markdown(tabela.rename(columns=titulos)),
        "",
    ]
    (DIR_RESULTADOS / "respostas_negocio.md").write_text(
        "\n".join(markdown), encoding="utf-8"
    )

    for linha in tabela.itertuples(index=False):
        print(f"\n{linha.numero}. {linha.pergunta}\n"
              f"   -> {linha.resposta} | {linha.metrica}\n"
              f"      {linha.observacao}")


def main() -> None:
    for pasta in (DIR_RESULTADOS, DIR_GRAFICOS, DIR_TABELAS):
        pasta.mkdir(parents=True, exist_ok=True)
    configurar_estilo()

    df = pd.read_csv(ARQUIVO_CSV_TRATADO, parse_dates=["data_venda"])
    caminho = ARQUIVO_CSV_TRATADO.relative_to(RAIZ_PROJETO)
    print(f"{len(df)} registros lidos de {caminho}")
    df = traduzir_categorias(df)

    print("\n=== Estatística descritiva ===")
    estatistica_descritiva(df)
    frequencias_categoricas(df)

    print("\n=== Respostas de negócio e gráficos ===")
    respostas = [
        p1_filial_maior_faturamento(df),
        p2_filial_mais_vendas(df),
        p3_linha_maior_faturamento(df),
        p4_linha_melhor_avaliacao(df),
        p5_forma_pagamento(df),
        *p6_p7_valor_vendas(df),
        p8_dia_semana(df),
    ]
    salvar_respostas(respostas)


if __name__ == "__main__":
    main()
