with
    fonte as (
        select *
        from {{ source('adventure_works', 'specialoffer') }}
    )

    , renomeado as (
        select
            cast(specialofferid as int) as pk_oferta_especial
            , cast(description as string) as descricao_oferta
            , cast(discountpct as decimal(10, 4)) as percentual_desconto
            , cast(type as string) as tipo_oferta
            , cast(category as string) as categoria_oferta
            , cast(startdate as timestamp) as data_inicio
            , cast(enddate as timestamp) as data_fim
            , cast(minqty as int) as quantidade_minima
            , cast(maxqty as int) as quantidade_maxima
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
