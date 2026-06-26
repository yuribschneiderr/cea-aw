with
    fonte as (
        select *
        from {{ source('adventure_works', 'stateprovince') }}
    )

    , renomeado as (
        select
            cast(stateprovinceid as int) as pk_estado_provincia
            , cast(stateprovincecode as string) as codigo_estado
            , cast(countryregioncode as string) as fk_pais_regiao
            , cast(isonlystateprovinceflag as boolean) as flag_unico_estado
            , cast(name as string) as nome_estado
            , cast(territoryid as int) as fk_territorio
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
