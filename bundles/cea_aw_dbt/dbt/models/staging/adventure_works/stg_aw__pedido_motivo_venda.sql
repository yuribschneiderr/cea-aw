with
    fonte as (
        select *
        from {{ source('adventure_works', 'salesorderheadersalesreason') }}
    )

    , renomeado as (
        select
            cast(salesorderid as int) as fk_pedido_venda
            , cast(salesreasonid as int) as fk_motivo_venda
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
