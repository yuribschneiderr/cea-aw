with
    fonte as (
        select *
        from {{ source('adventure_works', 'address') }}
    )

    , renomeado as (
        select
            cast(addressid as int) as pk_endereco
            , cast(addressline1 as string) as endereco_linha1
            , cast(addressline2 as string) as endereco_linha2
            , cast(city as string) as cidade
            , cast(stateprovinceid as int) as fk_estado_provincia
            , cast(postalcode as string) as cep
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
