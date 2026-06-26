with
    metodos_envio as (
        select *
        from {{ ref('stg_aw__metodos_envio') }}
    )

select *
from metodos_envio
