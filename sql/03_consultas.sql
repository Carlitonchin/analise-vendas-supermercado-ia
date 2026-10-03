-- =============================================================================
-- Fase 2 - Consultas SQL fundamentais e exportação para CSV
--
-- Execução (OBRIGATORIAMENTE a partir da raiz do projeto, pois o \copy grava
-- os arquivos em caminhos relativos):
--     psql -h localhost -U postgres -d vendas_supermercado -f sql/03_consultas.sql
--
-- Pré-requisito: raw_vendas carregada (python src/01_leitura_dados.py).
-- =============================================================================

\set ON_ERROR_STOP on

-- -----------------------------------------------------------------------------
-- Visão temporária (existe apenas nesta sessão) que converte os textos da
-- camada Raw para tipos numéricos e de data/hora. A tabela raw_vendas não é
-- alterada: a conversão acontece somente na leitura.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TEMP VIEW vw_vendas AS
SELECT
    invoice_id                                  AS id_venda,
    branch                                      AS filial,
    city                                        AS cidade,
    customer_type                               AS tipo_cliente,
    gender                                      AS genero,
    product_line                                AS linha_produto,
    unit_price::NUMERIC                         AS preco_unitario,
    quantity::INTEGER                           AS quantidade,
    tax_5_percent::NUMERIC                      AS imposto,
    sales::NUMERIC                              AS valor_total,
    TO_DATE(date, 'MM/DD/YYYY')                 AS data_venda,
    TO_TIMESTAMP(time, 'HH12:MI:SS AM')::TIME   AS hora_venda,
    payment                                     AS forma_pagamento,
    cogs::NUMERIC                               AS custo_mercadoria,
    gross_income::NUMERIC                       AS receita_bruta,
    rating::NUMERIC                             AS avaliacao
FROM raw_vendas;


\echo '\n==== 1. Visão geral da camada Raw ===='
SELECT COUNT(*)                 AS total_registros,
       COUNT(DISTINCT id_venda) AS vendas_distintas,
       MIN(data_venda)          AS primeira_venda,
       MAX(data_venda)          AS ultima_venda
FROM vw_vendas;


\echo '\n==== 2. Amostra dos dados brutos (SELECT + ORDER BY + LIMIT) ===='
SELECT invoice_id, branch, city, product_line, unit_price, quantity, sales, date, time, payment
FROM raw_vendas
ORDER BY linha_arquivo
LIMIT 5;


\echo '\n==== 3. Filtro (WHERE + AND): vendas acima de 900 na filial Giza pagas com Ewallet ===='
SELECT id_venda, filial, linha_produto, quantidade, valor_total, data_venda
FROM vw_vendas
WHERE filial = 'Giza'
  AND forma_pagamento = 'Ewallet'
  AND valor_total > 900
ORDER BY valor_total DESC;


\echo '\n==== 4. Filtro (WHERE + BETWEEN + IN): vendas de março bem avaliadas (>= 9.5) em alimentos e saúde ===='
SELECT id_venda, filial, linha_produto, valor_total, data_venda, avaliacao
FROM vw_vendas
WHERE data_venda BETWEEN DATE '2019-03-01' AND DATE '2019-03-31'
  AND linha_produto IN ('Food and beverages', 'Health and beauty')
  AND avaliacao >= 9.5
ORDER BY data_venda;


\echo '\n==== 5. [P1] Faturamento por filial (SUM + GROUP BY) ===='
SELECT filial,
       cidade,
       ROUND(SUM(valor_total), 2) AS faturamento
FROM vw_vendas
GROUP BY filial, cidade
ORDER BY faturamento DESC;


\echo '\n==== 6. [P2] Quantidade de vendas por filial (COUNT + GROUP BY) ===='
SELECT filial,
       COUNT(*)         AS quantidade_vendas,
       SUM(quantidade)  AS unidades_vendidas
FROM vw_vendas
GROUP BY filial
ORDER BY quantidade_vendas DESC;


\echo '\n==== 7. [P3] Faturamento por linha de produto ===='
SELECT linha_produto,
       ROUND(SUM(valor_total), 2) AS faturamento
FROM vw_vendas
GROUP BY linha_produto
ORDER BY faturamento DESC;


\echo '\n==== 8. [P4] Avaliação média por linha de produto (AVG) ===='
SELECT linha_produto,
       ROUND(AVG(avaliacao), 2) AS avaliacao_media
FROM vw_vendas
GROUP BY linha_produto
ORDER BY avaliacao_media DESC;


\echo '\n==== 9. [P5] Forma de pagamento mais utilizada ===='
SELECT forma_pagamento,
       COUNT(*) AS quantidade_vendas,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS percentual
FROM vw_vendas
GROUP BY forma_pagamento
ORDER BY quantidade_vendas DESC;


\echo '\n==== 10. [P6] Valor médio das vendas (AVG, MIN, MAX, SUM) ===='
SELECT ROUND(AVG(valor_total), 2) AS valor_medio,
       ROUND(MIN(valor_total), 2) AS menor_venda,
       ROUND(MAX(valor_total), 2) AS maior_venda,
       ROUND(SUM(valor_total), 2) AS faturamento_total
FROM vw_vendas;


\echo '\n==== 11. [P7] Maior venda registrada (subconsulta com MAX) ===='
SELECT id_venda, filial, cidade, linha_produto, preco_unitario, quantidade,
       valor_total, data_venda, forma_pagamento
FROM vw_vendas
WHERE valor_total = (SELECT MAX(valor_total) FROM vw_vendas);


\echo '\n==== 12. [P8] Quantidade de vendas por dia da semana ===='
SELECT EXTRACT(ISODOW FROM data_venda) AS numero_dia,
       CASE EXTRACT(ISODOW FROM data_venda)
           WHEN 1 THEN 'Segunda-feira'
           WHEN 2 THEN 'Terça-feira'
           WHEN 3 THEN 'Quarta-feira'
           WHEN 4 THEN 'Quinta-feira'
           WHEN 5 THEN 'Sexta-feira'
           WHEN 6 THEN 'Sábado'
           WHEN 7 THEN 'Domingo'
       END AS dia_semana,
       COUNT(*) AS quantidade_vendas
FROM vw_vendas
GROUP BY numero_dia, dia_semana
ORDER BY quantidade_vendas DESC;


\echo '\n==== 13. Filtro de grupos (HAVING): linhas de produto com faturamento acima de 54.000 ===='
SELECT linha_produto,
       COUNT(*)                   AS quantidade_vendas,
       ROUND(SUM(valor_total), 2) AS faturamento
FROM vw_vendas
GROUP BY linha_produto
HAVING SUM(valor_total) > 54000
ORDER BY faturamento DESC;


\echo '\n==== 14. Faturamento e ticket médio por mês ===='
SELECT TO_CHAR(data_venda, 'YYYY-MM')  AS mes,
       COUNT(*)                        AS quantidade_vendas,
       ROUND(SUM(valor_total), 2)      AS faturamento,
       ROUND(AVG(valor_total), 2)      AS ticket_medio
FROM vw_vendas
GROUP BY mes
ORDER BY mes;


-- =============================================================================
-- Exportação para CSV
-- O \copy (psql) grava o arquivo no computador do cliente, sem exigir permissão
-- de superusuário no servidor. Como o comando precisa caber em uma única linha,
-- as consultas longas ficam em visões temporárias.
-- =============================================================================

-- Exportação 1: dados brutos completos, com o cabeçalho original, para a etapa
-- de transformação no Pandas (src/02_etl_vendas.py).
CREATE OR REPLACE TEMP VIEW vw_exportacao_raw AS
SELECT invoice_id              AS "Invoice ID",
       branch                  AS "Branch",
       city                    AS "City",
       customer_type           AS "Customer type",
       gender                  AS "Gender",
       product_line            AS "Product line",
       unit_price              AS "Unit price",
       quantity                AS "Quantity",
       tax_5_percent           AS "Tax 5%",
       sales                   AS "Sales",
       date                    AS "Date",
       time                    AS "Time",
       payment                 AS "Payment",
       cogs                    AS "cogs",
       gross_margin_percentage AS "gross margin percentage",
       gross_income            AS "gross income",
       rating                  AS "Rating"
FROM raw_vendas
ORDER BY linha_arquivo;

\echo '\n==== Exportando dados brutos para data/raw/vendas_raw_exportadas.csv ===='
\copy (SELECT * FROM vw_exportacao_raw) TO 'data/raw/vendas_raw_exportadas.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

-- Exportação 2: resumo consolidado por filial (resultado de consulta agregada).
CREATE OR REPLACE TEMP VIEW vw_resumo_filiais AS
SELECT filial,
       cidade,
       COUNT(*)                   AS quantidade_vendas,
       SUM(quantidade)            AS unidades_vendidas,
       ROUND(SUM(valor_total), 2) AS faturamento,
       ROUND(AVG(valor_total), 2) AS ticket_medio,
       ROUND(AVG(avaliacao), 2)   AS avaliacao_media
FROM vw_vendas
GROUP BY filial, cidade
ORDER BY faturamento DESC;

\echo '\n==== Exportando resumo por filial para resultados/tabelas/sql_resumo_filiais.csv ===='
\copy (SELECT * FROM vw_resumo_filiais) TO 'resultados/tabelas/sql_resumo_filiais.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
