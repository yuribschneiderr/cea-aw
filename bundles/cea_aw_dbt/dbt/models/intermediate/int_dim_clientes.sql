with
    clientes as (
        select *
        from {{ ref('stg_aw__clientes') }}
    )

    , pessoas as (
        select *
        from {{ ref('stg_aw__pessoas') }}
    )

    , entidade_endereco as (
        select *
        from {{ ref('stg_aw__entidade_negocio_endereco') }}
    )

    , enderecos as (
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
    
    , territorios as (
        select *
        from {{ ref('stg_aw__territorios_venda') }}
    )

    , cliente_enriquecido as (
        select
            clientes.pk_cliente
            , pessoas.primeiro_nome || ' ' || coalesce(pessoas.nome_meio || ' ', '') || pessoas.ultimo_nome as nome_cliente
            , pessoas.tipo_pessoa
            , pessoas.promocao_email
            , enderecos.cidade
            , enderecos.cep
            , estados.nome_estado as estado
            , estados.codigo_estado
            , paises.nome_pais as pais
            , territorios.nome_territorio
            , territorios.grupo_territorio
        from clientes
        left join pessoas
            on clientes.fk_pessoa = pessoas.pk_pessoa
        left join entidade_endereco
            on pessoas.pk_pessoa = entidade_endereco.fk_entidade_negocio
        left join enderecos
            on entidade_endereco.fk_endereco = enderecos.pk_endereco
        left join estados
            on enderecos.fk_estado_provincia = estados.pk_estado_provincia
        left join paises
            on estados.fk_pais_regiao = paises.pk_pais_regiao
        left join territorios
            on clientes.fk_territorio = territorios.pk_territorio
    )

    -- Deduplica clientes que possuem múltiplos endereços (mantém o primeiro)
    , cliente_deduplicado as (
        select
            *
            , row_number() over (partition by pk_cliente order by cidade) as rn
        from cliente_enriquecido
    )

select
    pk_cliente
    , nome_cliente
    , tipo_pessoa
    , promocao_email
    , cidade
    , cep
    , estado
    , codigo_estado
    , pais
    , nome_territorio
    , grupo_territorio
from cliente_deduplicado
where rn = 1
