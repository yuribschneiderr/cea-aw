with
    fonte as (
        select *
        from {{ source('adventure_works', 'salesterritory') }}
    )

    , renomeado as (
        select
            cast(territoryid as int) as pk_territorio
            , cast(name as string) as nome_territorio
            , cast(countryregioncode as string) as fk_pais_regiao
            , cast("group" as string) as grupo_territorio
            , cast(salesytd as decimal(18, 2)) as vendas_ano_atual
            , cast(saleslastyear as decimal(18, 2)) as vendas_ano_anterior
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
