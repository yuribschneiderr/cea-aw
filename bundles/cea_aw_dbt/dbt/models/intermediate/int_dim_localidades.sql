-- Location dimension at address grain: city, state and country of each address.
-- The fact links to it through the ship-to address of the order.
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
