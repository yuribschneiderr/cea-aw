with
    fonte as (
        select *
        from {{ source('adventure_works', 'shipmethod') }}
    )

    , renomeado as (
        select
            cast(shipmethodid as int) as pk_metodo_envio
            , cast(name as string) as nome_metodo_envio
            , cast(shipbase as decimal(18, 2)) as taxa_base_envio
            , cast(shiprate as decimal(18, 2)) as taxa_envio
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
