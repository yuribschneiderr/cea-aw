with
    clientes as (
        select *
        from {{ ref('stg_aw__clientes') }}
    )

    , pessoas as (
        select *
        from {{ ref('stg_aw__pessoas') }}
    )

    , territorios as (
        select *
        from {{ ref('stg_aw__territorios_venda') }}
    )

    -- A localização (cidade, estado, país) NÃO fica aqui de propósito: clientes do tipo loja não têm
    -- endereço pessoal, então ela vem do endereço de entrega de cada pedido (ver int_dim_localidades).
    , cliente_enriquecido as (
        select
            clientes.pk_cliente
            , pessoas.primeiro_nome || ' ' || coalesce(pessoas.nome_meio || ' ', '') || pessoas.ultimo_nome as nome_cliente
            , pessoas.tipo_pessoa
            , pessoas.promocao_email
            , territorios.nome_territorio
            , territorios.grupo_territorio
        from clientes
        left join pessoas
            on clientes.fk_pessoa = pessoas.pk_pessoa
        left join territorios
            on clientes.fk_territorio = territorios.pk_territorio
    )

select *
from cliente_enriquecido
