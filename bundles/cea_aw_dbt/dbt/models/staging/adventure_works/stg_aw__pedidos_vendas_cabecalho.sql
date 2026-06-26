with
    fonte as (
        select *
        from {{ source('adventure_works', 'salesorderheader') }}
    )

    , renomeado as (
        select
            cast(salesorderid as int) as pk_pedido_venda
            , cast(revisionnumber as int) as numero_revisao
            , cast(orderdate as timestamp) as data_pedido
            , cast(duedate as timestamp) as data_vencimento
            , cast(shipdate as timestamp) as data_envio
            , cast(status as int) as status_pedido
            , cast(onlineorderflag as boolean) as flag_pedido_online
            , cast(purchaseordernumber as string) as numero_pedido_compra
            , cast(accountnumber as string) as numero_conta
            , cast(customerid as int) as fk_cliente
            , cast(salespersonid as int) as fk_vendedor
            , cast(territoryid as int) as fk_territorio
            , cast(billtoaddressid as int) as fk_endereco_cobranca
            , cast(shiptoaddressid as int) as fk_endereco_envio
            , cast(shipmethodid as int) as fk_metodo_envio
            , cast(creditcardid as int) as fk_cartao_credito
            , cast(creditcardapprovalcode as string) as codigo_aprovacao_cartao
            , cast(currencyrateid as int) as fk_taxa_cambio
            , cast(subtotal as decimal(18, 2)) as subtotal
            , cast(taxamt as decimal(18, 2)) as valor_imposto
            , cast(freight as decimal(18, 2)) as valor_frete
            , cast(totaldue as decimal(18, 2)) as valor_total_devido
            , cast(modifieddate as timestamp) as data_modificacao

        from fonte
    )

select *
from renomeado
