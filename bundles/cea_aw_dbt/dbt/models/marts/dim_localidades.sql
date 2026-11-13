with
    localidades as (
        select *
        from {{ ref('int_dim_localidades') }}
    )

select *
from localidades
