"""Configurações compartilhadas do pipeline: caminhos, fonte dos dados e credenciais.

As credenciais do PostgreSQL são lidas do arquivo .env (fora do controle de versão).
Use o .env.example como modelo.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROJETO / ".env")

# Pastas do projeto
DIR_DADOS_RAW = RAIZ_PROJETO / "data" / "raw"
DIR_DADOS_PROCESSADOS = RAIZ_PROJETO / "data" / "processed"
DIR_RESULTADOS = RAIZ_PROJETO / "resultados"
DIR_GRAFICOS = DIR_RESULTADOS / "graficos"
DIR_TABELAS = DIR_RESULTADOS / "tabelas"

# Arquivos de cada camada
ARQUIVO_CSV_ORIGINAL = DIR_DADOS_RAW / "supermarket_sales.csv"
ARQUIVO_CSV_EXPORTADO = DIR_DADOS_RAW / "vendas_raw_exportadas.csv"
ARQUIVO_CSV_TRATADO = DIR_DADOS_PROCESSADOS / "vendas_tratadas.csv"

# Fonte pública do dataset Supermarket Sales (Kaggle), espelhada no Google Drive
URL_DATASET = (
    "https://drive.usercontent.google.com/download"
    "?id=1B_EbKoR7mYiSa88fIrpiE02TViFUeOft&export=download&confirm=t"
)

# Cabeçalho do CSV original -> coluna da tabela raw_vendas (mesma ordem)
COLUNAS_RAW = {
    "Invoice ID": "invoice_id",
    "Branch": "branch",
    "City": "city",
    "Customer type": "customer_type",
    "Gender": "gender",
    "Product line": "product_line",
    "Unit price": "unit_price",
    "Quantity": "quantity",
    "Tax 5%": "tax_5_percent",
    "Sales": "sales",
    "Date": "date",
    "Time": "time",
    "Payment": "payment",
    "cogs": "cogs",
    "gross margin percentage": "gross_margin_percentage",
    "gross income": "gross_income",
    "Rating": "rating",
}


def credenciais_banco() -> dict:
    """Retorna os parâmetros de conexão com o PostgreSQL definidos no .env."""
    senha = os.getenv("DB_PASSWORD")
    if not senha:
        raise RuntimeError(
            "Variável DB_PASSWORD não definida. Copie o .env.example para .env "
            "e preencha as credenciais do PostgreSQL."
        )
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "vendas_supermercado"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": senha,
    }
