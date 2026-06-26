-- Gera a dimensão de datas a partir do range dos pedidos de venda
with
    pedidos as (
        select
            min(data_pedido) as data_minima
            , max(data_pedido) as data_maxima
        from {{ ref('stg_aw__pedidos_vendas_cabecalho') }}
    )

    , sequencia_datas as (
        select
            explode(
                sequence(
                    cast((select data_minima from pedidos) as date),
                    cast((select data_maxima from pedidos) as date),
                    interval 1 day
                )
            ) as data_completa
    )

    , dimensao_datas as (
        select
            cast(date_format(data_completa, 'yyyyMMdd') as int) as pk_data
            , data_completa as data_completa
            , year(data_completa) as ano
            , month(data_completa) as mes
            , day(data_completa) as dia
            , quarter(data_completa) as trimestre
            , dayofweek(data_completa) as dia_semana
            , date_format(data_completa, 'EEEE') as nome_dia_semana
            , date_format(data_completa, 'MMMM') as nome_mes
            , concat(year(data_completa), '-Q', quarter(data_completa)) as ano_trimestre
            , date_format(data_completa, 'yyyy-MM') as ano_mes
            , case
                when dayofweek(data_completa) in (1, 7) then true
                else false
              end as flag_fim_semana

        from sequencia_datas
    )

select *
from dimensao_datas
