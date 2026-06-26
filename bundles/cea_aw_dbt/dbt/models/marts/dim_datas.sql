with
    datas as (
        select *
        from {{ ref('int_dim_datas') }}
    )

select *
from datas
