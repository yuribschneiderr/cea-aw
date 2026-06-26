with
    produtos as (
        select *
        from {{ ref('stg_aw__produtos') }}
    )

    , subcategorias as (
        select *
        from {{ ref('stg_aw__subcategorias_produto') }}
    )

    , categorias as (
        select *
        from {{ ref('stg_aw__categorias_produto') }}
    )

    , produto_enriquecido as (
        select
            produtos.pk_produto
            , produtos.nome_produto
            , produtos.numero_produto
            , produtos.cor
            , produtos.tamanho
            , produtos.peso
            , produtos.custo_padrao
            , produtos.preco_lista
            , produtos.linha_produto
            , produtos.classe
            , produtos.estilo
            , produtos.dias_fabricacao
            , produtos.flag_fabricacao_propria
            , produtos.flag_produto_acabado
            , produtos.data_inicio_venda
            , produtos.data_fim_venda
            , subcategorias.nome_subcategoria
            , categorias.nome_categoria
        from produtos
        left join subcategorias
            on produtos.fk_subcategoria_produto = subcategorias.pk_subcategoria_produto
        left join categorias
            on subcategorias.fk_categoria_produto = categorias.pk_categoria_produto
    )

select *
from produto_enriquecido
