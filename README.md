# CEA-AW: Analytics Engineering Pipeline - Adventure Works

Este projeto implementa um pipeline completo de Analytics Engineering utilizando dados da empresa fictícia Adventure Works. O pipeline engloba desde a extração de dados transacionais, transformação via dbt com arquitetura em camadas (Medallion / Dimensional), até a orquestração utilizando Databricks Asset Bundles (DABs).

## Arquitetura e Stack Tecnológica

O projeto foi construído usando as seguintes ferramentas:
- **PostgreSQL**: Serviu como banco de dados transacional (OLTP) de origem, simulando um ambiente produtivo.
- **Databricks (Lakehouse)**: Plataforma principal de processamento e armazenamento (Delta Lake).
- **dbt (Data Build Tool)**: Ferramenta responsável pela modelagem, transformação e testes de qualidade de dados.
- **Databricks Asset Bundles (DABs)**: Ferramenta de orquestração CI/CD (Infrastructure as Code) para deploy de jobs no Databricks.

## Modelagem de Dados

Optamos por uma modelagem dimensional estruturada nas seguintes camadas, respeitando as melhores práticas do dbt:

1. **Staging (Bronze/Raw):**
   - Importação direta das tabelas fonte (`adventure_works`), renomeando as colunas para um formato padronizado (snake_case e em Português) e fazendo o cast explícito de tipos de dados.
   - Aplicação de testes de integridade básica (`unique`, `not_null`) em chaves primárias.

2. **Intermediate (Prata/Silver):**
   - Junções (JOINs) entre entidades altamente normalizadas (ex: `Customer` + `Person` + `SalesTerritory`, `Address` + `StateProvince` + `CountryRegion`).
   - Geração de uma espinha dorsal de datas (Date Spine) construída dinamicamente.
   - Desnormalização e agregação (ex: concatenar múltiplos motivos de venda num mesmo pedido).

3. **Marts (Ouro/Gold):**
   - Criação do **Star Schema** focado nas análises de vendas, expondo Views/Tables amigáveis ao negócio:
     - Fatos: `fct_pedidos_vendas` (com as chaves estrangeiras, métricas de negócio, tipos de cartão e motivos agregados).
     - Dimensões: `dim_clientes` (com território de vendas), `dim_localidades` (cidade, estado e país do endereço de entrega do pedido), `dim_produtos` (com categorias e subcategorias), `dim_datas`, `dim_metodos_envio`, `dim_ofertas_especiais`.
   - A localização vem do endereço de entrega do pedido, e não do cadastro do cliente: clientes do tipo loja não possuem endereço pessoal, enquanto todo pedido possui endereço de entrega.

### Diagrama do Modelo Dimensional (Star Schema)

```mermaid
erDiagram
    fct_pedidos_vendas }|--|| dim_clientes : "fk_cliente"
    fct_pedidos_vendas }|--|| dim_localidades : "fk_localidade"
    fct_pedidos_vendas }|--|| dim_produtos : "fk_produto"
    fct_pedidos_vendas }|--|| dim_datas : "fk_data"
    fct_pedidos_vendas }|--|| dim_metodos_envio : "fk_metodo_envio"
    fct_pedidos_vendas }|--|| dim_ofertas_especiais : "fk_oferta_especial"

    fct_pedidos_vendas {
        int pk_pedido_venda_detalhe PK
        int fk_pedido_venda
        int fk_data FK
        int fk_cliente FK
        int fk_localidade FK
        int fk_metodo_envio FK
        int fk_produto FK
        int fk_oferta_especial FK
        timestamp data_pedido
        string descricao_status
        int quantidade
        decimal preco_unitario
        decimal desconto_unitario
        decimal valor_bruto_linha
        decimal valor_desconto_linha
        decimal valor_total_linha
        string tipo_cartao
        string motivos_venda
    }

    dim_clientes {
        int pk_cliente PK
        string nome_cliente
        string tipo_pessoa
        string nome_territorio
        string grupo_territorio
    }

    dim_localidades {
        int pk_localidade PK
        string cidade
        string estado
        string pais
    }

    dim_produtos {
        int pk_produto PK
        string nome_produto
        string nome_subcategoria
        string nome_categoria
    }
```

## Qualidade e Testes de Dados

Para garantir a confiabilidade analítica, implementamos:
- Testes genéricos (chaves primárias únicas e não nulas).
- Relacionamentos mapeados nos arquivos `schema.yml` da camada Marts garantindo a Integridade Referencial.
- **Auditoria de Negócio (Singular Test):** Teste contábil auditando que o valor total de vendas brutas (Gross Sales) no ano de 2011 resultou exatamente no montante validado de **$12,646,112.16**.

## Como Executar o Projeto

1. **Configuração e Ingestão:**
   Foi criado um script (`ingest_databricks.sh`) que extrai dados do PostgreSQL e envia via Databricks CLI para um Volume (`workspace.adventure_works.raw_data`). Depois, via SQL Editor do Databricks, as tabelas Delta são criadas a partir dos arquivos CSV.

2. **Deploy do Bundle:**
   Faça o deploy do código para o Databricks utilizando a CLI do Databricks:
   ```bash
   databricks bundle deploy --target dev
   ```

3. **Execução do Job (dbt build):**
   Rode o job do dbt remotamente no serverless SQL do Databricks:
   ```bash
   databricks bundle run cea_aw_dbt_job --target dev
   ```

## Dashboard de Negócios

Com as tabelas consolidadas geradas pela camada Marts no schema `dev_cea_aw_marts`, o dashboard atende às necessidades dos diretores e partes interessadas, fornecendo métricas estratégicas, como:
- Número de pedidos, quantidade comprada e valor total negociado.
- Análise de tickets médios (mensal, mensal por canal e anual por país).
- Top 20 produtos, Top 20 estados, Top 10 clientes e Top 5 cidades com mais faturamento.
- Série temporal mensal de faturamento e pedidos.
- Produtos mais vendidos com o motivo de venda "Promotion".

O dashboard foi organizado como uma narrativa: cada página responde a uma pergunta e cada seção a uma pergunta menor. **Visão geral** (como está o negócio: indicadores, evolução mensal do faturamento explicada por pedidos × ticket médio, participação por canal e categoria), **Análise por dimensão** (o que, onde e para quem vendemos: produtos, localização, clientes, motivo de venda, tipo de cartão e status) e **Análises avançadas** (por quê: Pareto de produtos e de clientes em barras + linha acumulada, curva ABC de produtos, efeito do motivo "Promotion" e dos descontos, papel de cada canal e recorrência de clientes). Os filtros são globais e valem para todas as páginas: período, produto, cliente, tipo de cartão, motivo de venda, status, cidade, estado, país e canal de venda. A exceção são os rankings (Top 20 produtos, Top 20 estados, Top 10 clientes, Top 5 cidades e produtos do motivo "Promotion") e as curvas de Pareto, que são calculados na própria consulta SQL: eles são recalculados para o período selecionado (por meio de um parâmetro de data aplicado antes do agrupamento) e respondem apenas ao filtro de período. A definição do dashboard é versionada em `bundles/cea_aw_dbt/src/cea_aw_dashboard.lvdash.json` e publicada pelo `databricks bundle deploy`.
