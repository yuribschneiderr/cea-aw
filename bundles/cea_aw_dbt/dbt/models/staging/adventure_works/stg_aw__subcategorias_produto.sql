with
    fonte as (
        select *
        from {{ source('adventure_works', 'productsubcategory') }}
    )

    , renomeado as (
        select
            cast(productsubcategoryid as int) as pk_subcategoria_produto
            , cast(productcategoryid as int) as fk_categoria_produto
            , cast(name as string) as nome_subcategoria
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
