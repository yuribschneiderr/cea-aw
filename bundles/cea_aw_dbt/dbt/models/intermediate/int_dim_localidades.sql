-- Dimensão de localidade no grão de endereço: cidade, estado e país de cada endereço.
-- A fato se liga a ela pelo endereço de entrega do pedido.
with
    enderecos as (
        select *
        from {{ ref('stg_aw__enderecos') }}
    )

    , estados as (
        select *
        from {{ ref('stg_aw__estados_provincias') }}
    )

    , paises as (
        select *
        from {{ ref('stg_aw__paises_regioes') }}
    )

    , localidade as (
        select
            enderecos.pk_endereco as pk_localidade
            , enderecos.cidade
            , enderecos.cep
            , estados.nome_estado as estado
            , estados.codigo_estado
            , paises.nome_pais as pais
            , paises.pk_pais_regiao as codigo_pais
        from enderecos
        left join estados
            on enderecos.fk_estado_provincia = estados.pk_estado_provincia
        left join paises
            on estados.fk_pais_regiao = paises.pk_pais_regiao
    )

select *
from localidade
