with
    ofertas as (
        select *
        from {{ ref('stg_aw__ofertas_especiais') }}
    )

select *
from ofertas
