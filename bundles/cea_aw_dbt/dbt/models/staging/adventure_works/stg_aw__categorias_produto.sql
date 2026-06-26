with
    fonte as (
        select *
        from {{ source('adventure_works', 'productcategory') }}
    )

    , renomeado as (
        select
            cast(productcategoryid as int) as pk_categoria_produto
            , cast(name as string) as nome_categoria
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
