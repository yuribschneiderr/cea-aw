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

    -- Uma linha por pedido, com seus motivos de venda unidos em um único texto separado por vírgula.
    -- O array_sort torna o resultado determinístico (o collect_list sozinho não garante a ordem).
    , motivos_agregados as (
        select
            pm.fk_pedido_venda
            , array_join(array_sort(collect_list(m.nome_motivo)), ', ') as motivos_venda
        from pedido_motivo pm
        left join motivos m on pm.fk_motivo_venda = m.pk_motivo_venda
        group by pm.fk_pedido_venda
    )

    , pedido_completo as (
        select
            detalhe.pk_pedido_venda_detalhe
            -- Dimensão degenerada: número do pedido, usado para contar pedidos distintos
            , cabecalho.pk_pedido_venda as fk_pedido_venda
            , cast(date_format(cabecalho.data_pedido, 'yyyyMMdd') as int) as fk_data
            , cabecalho.fk_cliente
            -- A localização vem do endereço de entrega do pedido (todo pedido tem um)
            , cabecalho.fk_endereco_envio as fk_localidade
            , cabecalho.fk_metodo_envio
            , detalhe.fk_produto
            , detalhe.fk_oferta_especial
            , cabecalho.data_pedido
            , cabecalho.data_vencimento
            , cabecalho.data_envio
            , cabecalho.status_pedido
            , case cabecalho.status_pedido
                when 1 then 'Em processamento'
                when 2 then 'Aprovado'
                when 3 then 'Em espera'
                when 4 then 'Rejeitado'
                when 5 then 'Enviado'
                when 6 then 'Cancelado'
                else 'Desconhecido'
              end as descricao_status
            , cabecalho.flag_pedido_online
            , cabecalho.numero_pedido_compra
            , cabecalho.numero_conta
            , detalhe.quantidade
            , detalhe.preco_unitario
            , detalhe.desconto_unitario
            -- Métricas da linha (dicionário de dados): bruto = preço * qtd; líquido = bruto * (1 - desconto)
            , cast(detalhe.preco_unitario * detalhe.quantidade as decimal(38, 6)) as valor_bruto_linha
            , cast(
                detalhe.preco_unitario * detalhe.quantidade * detalhe.desconto_unitario as decimal(38, 6)
              ) as valor_desconto_linha
            , cast(
                detalhe.preco_unitario * detalhe.quantidade * (1 - detalhe.desconto_unitario) as decimal(38, 6)
              ) as valor_total_linha
            -- Valores do cabeçalho se repetem em todas as linhas do pedido: não somar no grão de linha
            , cabecalho.subtotal
            , cabecalho.valor_imposto
            , cabecalho.valor_frete
            , cabecalho.valor_total_devido

            -- Atributos desnormalizados na fato
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
