with
    fonte as (
        select *
        from {{ source('adventure_works', 'person') }}
    )

    , renomeado as (
        select
            cast(businessentityid as int) as pk_pessoa
            , cast(persontype as string) as tipo_pessoa
            , cast(title as string) as titulo
            , cast(firstname as string) as primeiro_nome
            , cast(middlename as string) as nome_meio
            , cast(lastname as string) as ultimo_nome
            , cast(suffix as string) as sufixo
            , cast(emailpromotion as int) as promocao_email
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
