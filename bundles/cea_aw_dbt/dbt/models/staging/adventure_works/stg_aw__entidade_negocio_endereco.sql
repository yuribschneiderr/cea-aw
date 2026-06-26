with
    fonte as (
        select *
        from {{ source('adventure_works', 'businessentityaddress') }}
    )

    , renomeado as (
        select
            cast(businessentityid as int) as fk_entidade_negocio
            , cast(addressid as int) as fk_endereco
            , cast(addresstypeid as int) as fk_tipo_endereco
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
