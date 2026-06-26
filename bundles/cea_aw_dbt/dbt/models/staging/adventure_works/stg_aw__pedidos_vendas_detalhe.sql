with
    fonte as (
        select *
        from {{ source('adventure_works', 'salesorderdetail') }}
    )

    , renomeado as (
        select
            cast(salesorderid as int) as fk_pedido_venda
            , cast(salesorderdetailid as int) as pk_pedido_venda_detalhe
            , cast(carriertrackingnumber as string) as numero_rastreamento
            , cast(orderqty as int) as quantidade
            , cast(productid as int) as fk_produto
            , cast(specialofferid as int) as fk_oferta_especial
            , cast(unitprice as decimal(18, 2)) as preco_unitario
            , cast(unitpricediscount as decimal(18, 4)) as desconto_unitario
            , cast(orderqty * unitprice * (1 - unitpricediscount) as decimal(38, 6)) as valor_total_linha
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
