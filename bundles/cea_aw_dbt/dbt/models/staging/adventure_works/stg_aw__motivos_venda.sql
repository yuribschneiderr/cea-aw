with
    fonte as (
        select *
        from {{ source('adventure_works', 'salesreason') }}
    )

    , renomeado as (
        select
            cast(salesreasonid as int) as pk_motivo_venda
            , cast(name as string) as nome_motivo
            , cast(reasontype as string) as tipo_motivo
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
