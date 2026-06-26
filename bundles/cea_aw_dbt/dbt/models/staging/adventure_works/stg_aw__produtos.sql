with
    fonte as (
        select *
        from {{ source('adventure_works', 'product') }}
    )

    , renomeado as (
        select
            cast(productid as int) as pk_produto
            , cast(name as string) as nome_produto
            , cast(productnumber as string) as numero_produto
            , cast(makeflag as boolean) as flag_fabricacao_propria
            , cast(finishedgoodsflag as boolean) as flag_produto_acabado
            , cast(color as string) as cor
            , cast(safetystocklevel as int) as nivel_estoque_seguranca
            , cast(reorderpoint as int) as ponto_reposicao
            , cast(standardcost as decimal(18, 2)) as custo_padrao
            , cast(listprice as decimal(18, 2)) as preco_lista
            , cast(size as string) as tamanho
            , cast(weight as decimal(8, 2)) as peso
            , cast(daystomanufacture as int) as dias_fabricacao
            , cast(productline as string) as linha_produto
            , cast(class as string) as classe
            , cast(style as string) as estilo
            , cast(productsubcategoryid as int) as fk_subcategoria_produto
            , cast(productmodelid as int) as fk_modelo_produto
            , cast(sellstartdate as timestamp) as data_inicio_venda
            , cast(sellenddate as timestamp) as data_fim_venda
            , cast(discontinueddate as timestamp) as data_descontinuacao
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
