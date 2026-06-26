-- Teste singular para garantir que as vendas brutas de 2011 batem com o valor auditado
-- Valor esperado: $ 12.646.112,16
-- No dbt, um teste passa se retornar 0 linhas. Se retornar qualquer linha, ele falha.

with
    vendas_2011 as (
        select
            round(sum(preco_unitario * quantidade), 2) as vendas_brutas
        from {{ ref('fct_pedidos_vendas') }}
        where year(data_pedido) = 2011
    )

select *
from vendas_2011
where vendas_brutas not between 12646105.00 and 12646113.00
