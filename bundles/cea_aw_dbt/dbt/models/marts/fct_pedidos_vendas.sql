with
    pedidos_vendas as (
        select *
        from {{ ref('int_fct_pedidos_vendas') }}
    )

select *
from pedidos_vendas
