with
    fonte as (
        select *
        from {{ source('adventure_works', 'personcreditcard') }}
    )

    , renomeado as (
        select
            cast(businessentityid as int) as fk_pessoa
            , cast(creditcardid as int) as fk_cartao_credito
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
