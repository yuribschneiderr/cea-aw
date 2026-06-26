with
    produtos as (
        select *
        from {{ ref('int_dim_produtos') }}
    )

select *
from produtos
