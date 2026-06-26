with
    fonte as (
        select *
        from {{ source('adventure_works', 'customer') }}
    )

    , renomeado as (
        select
            cast(customerid as int) as pk_cliente
            , cast(personid as int) as fk_pessoa
            , cast(storeid as int) as fk_loja
            , cast(territoryid as int) as fk_territorio
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
