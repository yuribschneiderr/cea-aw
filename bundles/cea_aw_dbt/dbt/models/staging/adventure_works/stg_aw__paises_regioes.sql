with
    fonte as (
        select *
        from {{ source('adventure_works', 'countryregion') }}
    )

    , renomeado as (
        select
            cast(countryregioncode as string) as pk_pais_regiao
            , cast(name as string) as nome_pais
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
