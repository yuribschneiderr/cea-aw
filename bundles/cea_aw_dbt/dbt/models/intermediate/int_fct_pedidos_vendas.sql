with
    cabecalho as (
        select *
        from {{ ref('stg_aw__pedidos_vendas_cabecalho') }}
    )

    , detalhe as (
        select *
        from {{ ref('stg_aw__pedidos_vendas_detalhe') }}
    )

    , pedido_motivo as (
        select *
        from {{ ref('stg_aw__pedido_motivo_venda') }}
    )

    , motivos as (
        select *
        from {{ ref('stg_aw__motivos_venda') }}
    )
    
    , cartoes as (
        select *
        from {{ ref('stg_aw__cartoes_credito') }}
    )

    -- Agrega os motivos de venda por pedido numa única string separada por vírgula
    , motivos_agregados as (
        select
            pm.fk_pedido_venda
            , array_join(collect_list(m.nome_motivo), ', ') as motivos_venda
        from pedido_motivo pm
        left join motivos m on pm.fk_motivo_venda = m.pk_motivo_venda
        group by pm.fk_pedido_venda
    )

    , pedido_completo as (
        select
            detalhe.pk_pedido_venda_detalhe
            , cabecalho.pk_pedido_venda
            , cast(date_format(cabecalho.data_pedido, 'yyyyMMdd') as int) as fk_data
            , cabecalho.fk_cliente
            , cabecalho.fk_metodo_envio
            , detalhe.fk_produto
            , detalhe.fk_oferta_especial
            , cabecalho.data_pedido
            , cabecalho.data_vencimento
            , cabecalho.data_envio
            , cabecalho.status_pedido
            , cabecalho.flag_pedido_online
            , cabecalho.numero_pedido_compra
            , cabecalho.numero_conta
            , detalhe.quantidade
            , detalhe.preco_unitario
            , detalhe.desconto_unitario
            , detalhe.valor_total_linha
            , cabecalho.subtotal
            , cabecalho.valor_imposto
            , cabecalho.valor_frete
            , cabecalho.valor_total_devido
            
            -- Dados desnormalizados diretamente na fato
            , coalesce(cartoes.tipo_cartao, 'N/A') as tipo_cartao
            , coalesce(motivos_agregados.motivos_venda, 'Nenhum') as motivos_venda

        from detalhe
        inner join cabecalho
            on detalhe.fk_pedido_venda = cabecalho.pk_pedido_venda
        left join cartoes
            on cabecalho.fk_cartao_credito = cartoes.pk_cartao_credito
        left join motivos_agregados
            on cabecalho.pk_pedido_venda = motivos_agregados.fk_pedido_venda
    )

select *
from pedido_completo
