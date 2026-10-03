-- =============================================================================
-- Fase 0 - Criação do banco de dados
-- Projeto : Análise de Vendas de Supermercado (dataset Supermarket Sales - Kaggle)
--
-- Execução (a partir da raiz do projeto, conectado ao banco padrão "postgres"):
--     psql -h localhost -U postgres -d postgres -f sql/01_criar_banco.sql
-- =============================================================================

-- O PostgreSQL não aceita "CREATE DATABASE IF NOT EXISTS". O SELECT abaixo gera
-- o comando somente quando o banco ainda não existe e o \gexec (psql) o executa,
-- deixando o script idempotente (pode ser executado mais de uma vez sem erro).
SELECT 'CREATE DATABASE vendas_supermercado
            WITH ENCODING = ''UTF8''
                 TEMPLATE = template0'
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_database
    WHERE datname = 'vendas_supermercado'
)\gexec

COMMENT ON DATABASE vendas_supermercado IS
    'Pipeline de vendas de supermercado: camada Raw (raw_vendas) e Tratada (vendas_tratadas).';

-- Conferência: o banco deve aparecer na listagem.
SELECT datname AS banco,
       pg_encoding_to_char(encoding) AS codificacao
FROM pg_database
WHERE datname = 'vendas_supermercado';
