with
    fonte as (
        select *
        from {{ source('adventure_works', 'creditcard') }}
    )

    , renomeado as (
        select
            cast(creditcardid as int) as pk_cartao_credito
            , cast(cardtype as string) as tipo_cartao
            , cast(cardnumber as string) as numero_cartao
            , cast(expmonth as int) as mes_expiracao
            , cast(expyear as int) as ano_expiracao
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
