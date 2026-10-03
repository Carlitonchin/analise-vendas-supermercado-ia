-- =============================================================================
-- Fase 0 - Criação das tabelas das camadas Raw e Tratada
--
-- Execução (a partir da raiz do projeto):
--     psql -h localhost -U postgres -d vendas_supermercado -f sql/02_criar_tabelas.sql
--
-- Atenção: as tabelas são recriadas do zero (DROP + CREATE) para garantir que a
-- estrutura sempre corresponda a este script. Os dados são recarregados pelos
-- scripts Python (src/01_leitura_dados.py e src/02_etl_vendas.py).
-- =============================================================================

DROP TABLE IF EXISTS vendas_tratadas;
DROP TABLE IF EXISTS raw_vendas;


-- -----------------------------------------------------------------------------
-- Camada RAW: cópia fiel do CSV original.
-- Todas as colunas de negócio são TEXT para que nenhum valor seja convertido,
-- arredondado ou rejeitado na carga. Os nomes seguem o cabeçalho original
-- (em snake_case), indicado entre aspas em cada comentário. As colunas de
-- controle garantem a rastreabilidade de cada registro até o arquivo e a
-- linha de onde ele veio.
-- -----------------------------------------------------------------------------
CREATE TABLE raw_vendas (
    id_raw                  INTEGER GENERATED ALWAYS AS IDENTITY,
    invoice_id              TEXT        NOT NULL,   -- "Invoice ID": identificador da venda
    branch                  TEXT,                   -- "Branch": filial
    city                    TEXT,                   -- "City": cidade
    customer_type           TEXT,                   -- "Customer type": tipo de cliente
    gender                  TEXT,                   -- "Gender": gênero
    product_line            TEXT,                   -- "Product line": linha de produto
    unit_price              TEXT,                   -- "Unit price": preço unitário
    quantity                TEXT,                   -- "Quantity": quantidade
    tax_5_percent           TEXT,                   -- "Tax 5%": imposto de 5%
    sales                   TEXT,                   -- "Sales": valor total da venda
    date                    TEXT,                   -- "Date": data (texto M/D/AAAA)
    time                    TEXT,                   -- "Time": hora (texto H:MM:SS AM/PM)
    payment                 TEXT,                   -- "Payment": forma de pagamento
    cogs                    TEXT,                   -- "cogs": custo das mercadorias vendidas
    gross_margin_percentage TEXT,                   -- "gross margin percentage": margem bruta (%)
    gross_income            TEXT,                   -- "gross income": receita bruta
    rating                  TEXT,                   -- "Rating": avaliação do cliente (0 a 10)

    -- Colunas de controle (rastreabilidade)
    arquivo_origem          TEXT        NOT NULL,
    linha_arquivo           INTEGER     NOT NULL,
    data_carga              TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_raw_vendas PRIMARY KEY (id_raw),
    CONSTRAINT uq_raw_vendas_origem UNIQUE (arquivo_origem, linha_arquivo),
    CONSTRAINT ck_raw_vendas_linha_arquivo CHECK (linha_arquivo > 1)  -- linha 1 é o cabeçalho
);

COMMENT ON TABLE raw_vendas IS
    'Camada Raw: dados brutos do CSV Supermarket Sales, sem nenhuma alteração de conteúdo.';
COMMENT ON COLUMN raw_vendas.arquivo_origem IS 'Nome do arquivo CSV de onde o registro foi lido.';
COMMENT ON COLUMN raw_vendas.linha_arquivo IS 'Número da linha no arquivo de origem (linha 1 = cabeçalho).';
COMMENT ON COLUMN raw_vendas.data_carga IS 'Momento em que o registro foi carregado no banco.';


-- -----------------------------------------------------------------------------
-- Camada TRATADA: dados limpos e tipados, conforme o dicionário de dados.
-- É carregada a partir de data/processed/vendas_tratadas.csv (gerado no Pandas).
-- -----------------------------------------------------------------------------
CREATE TABLE vendas_tratadas (
    id_venda            VARCHAR(50)     NOT NULL,
    filial              VARCHAR(10)     NOT NULL,
    cidade              VARCHAR(100)    NOT NULL,
    tipo_cliente        VARCHAR(50),
    genero              VARCHAR(20),
    linha_produto       VARCHAR(150)    NOT NULL,
    preco_unitario      NUMERIC(10, 2),
    quantidade          INTEGER,
    imposto             NUMERIC(10, 2),
    valor_total         NUMERIC(12, 2),
    data_venda          DATE,
    hora_venda          TIME,
    forma_pagamento     VARCHAR(50)     NOT NULL,
    custo_mercadoria    NUMERIC(12, 2),
    margem_percentual   NUMERIC(10, 2),
    receita_bruta       NUMERIC(12, 2),
    avaliacao           NUMERIC(4, 2),

    CONSTRAINT pk_vendas_tratadas PRIMARY KEY (id_venda),
    CONSTRAINT ck_vendas_tratadas_preco_unitario   CHECK (preco_unitario >= 0),
    CONSTRAINT ck_vendas_tratadas_quantidade       CHECK (quantidade > 0),
    CONSTRAINT ck_vendas_tratadas_imposto          CHECK (imposto >= 0),
    CONSTRAINT ck_vendas_tratadas_valor_total      CHECK (valor_total >= 0),
    CONSTRAINT ck_vendas_tratadas_custo_mercadoria CHECK (custo_mercadoria >= 0),
    CONSTRAINT ck_vendas_tratadas_receita_bruta    CHECK (receita_bruta >= 0),
    CONSTRAINT ck_vendas_tratadas_avaliacao        CHECK (avaliacao BETWEEN 0 AND 10)
);

COMMENT ON TABLE vendas_tratadas IS
    'Camada Tratada: vendas limpas e tipadas no Pandas (src/02_etl_vendas.py).';
COMMENT ON COLUMN vendas_tratadas.valor_total IS
    'Valor total da venda (preço unitário x quantidade + imposto), conferido no ETL.';
COMMENT ON COLUMN vendas_tratadas.data_venda IS 'Data da venda convertida de texto (M/D/AAAA) para DATE.';
COMMENT ON COLUMN vendas_tratadas.hora_venda IS 'Hora da venda convertida de texto (H:MM:SS AM/PM) para TIME.';


-- Conferência: tabelas criadas e suas restrições.
SELECT tc.table_name      AS tabela,
       tc.constraint_name AS restricao,
       tc.constraint_type AS tipo
FROM information_schema.table_constraints AS tc
WHERE tc.table_schema = 'public'
  AND tc.table_name IN ('raw_vendas', 'vendas_tratadas')
  AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'CHECK')
  AND tc.constraint_name NOT LIKE '%_not_null'
ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name;
