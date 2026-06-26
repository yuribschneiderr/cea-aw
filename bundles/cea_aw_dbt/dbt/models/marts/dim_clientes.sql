with
    clientes as (
        select *
        from {{ ref('int_dim_clientes') }}
    )

select *
from clientes
