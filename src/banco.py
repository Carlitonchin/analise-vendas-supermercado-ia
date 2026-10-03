"""Funções de acesso ao PostgreSQL reutilizadas pelos scripts do pipeline."""

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from config import credenciais_banco


def obter_conexao():
    """Abre uma conexão com o banco usando as credenciais do .env."""
    return psycopg2.connect(**credenciais_banco())


def recarregar_tabela(
    tabela: str, colunas: list[str], linhas: list[tuple]
) -> None:
    """Esvazia a tabela e insere as linhas informadas em uma única transação.

    Se qualquer linha violar uma restrição (NOT NULL, CHECK, PRIMARY KEY),
    a transação inteira é desfeita e a tabela permanece como estava.
    """
    comando_truncate = sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY").format(
        sql.Identifier(tabela)
    )
    comando_insert = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
        sql.Identifier(tabela),
        sql.SQL(", ").join(map(sql.Identifier, colunas)),
    )
    conexao = obter_conexao()
    try:
        with conexao, conexao.cursor() as cursor:
            cursor.execute(comando_truncate)
            execute_values(
                cursor, comando_insert.as_string(cursor), linhas, page_size=500
            )
    finally:
        conexao.close()


def consultar(comando: str) -> tuple[list[str], list[tuple]]:
    """Executa uma consulta e devolve (nomes das colunas, linhas)."""
    conexao = obter_conexao()
    try:
        with conexao, conexao.cursor() as cursor:
            cursor.execute(comando)
            colunas = [descricao[0] for descricao in cursor.description]
            return colunas, cursor.fetchall()
    finally:
        conexao.close()
