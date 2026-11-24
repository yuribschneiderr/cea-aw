# Databricks notebook source
# MAGIC %md
# MAGIC # Análise exploratória de dados (EDA) - Adventure Works
# MAGIC
# MAGIC **Objetivo:** conhecer os dados de vendas da Adventure Works antes de definir indicadores e gráficos. A análise verifica a qualidade da origem, valida o modelo dimensional e levanta os padrões de negócio que orientaram o dashboard.
# MAGIC
# MAGIC **Fontes**
# MAGIC - `workspace.adventure_works`: tabelas brutas, cópia do banco transacional (PostgreSQL).
# MAGIC - `workspace.dev_cea_aw_marts`: modelo dimensional gerado pelo dbt (`fct_pedidos_vendas` e as dimensões).
# MAGIC
# MAGIC **Definições (as mesmas do dashboard)**
# MAGIC - **Valor total negociado** = preço unitário × quantidade (valor bruto, antes dos descontos).
# MAGIC - **Valor líquido** = valor bruto − descontos.
# MAGIC - **Ticket médio** = valor líquido / número de pedidos.
# MAGIC - **Número de pedidos** = pedidos distintos (o número do pedido é a dimensão degenerada `fk_pedido_venda`).
# MAGIC - **Canal**: pedido online (cliente pessoa física) ou revenda (lojas, atendidas por vendedor).
# MAGIC
# MAGIC **Como executar:** conecte o notebook a um compute serverless e use *Run all*. Todas as consultas são somente leitura.
# MAGIC
# MAGIC **Roteiro**
# MAGIC 1. Inventário das tabelas de origem
# MAGIC 2. Qualidade dos dados
# MAGIC 3. Auditoria contábil: vendas brutas de 2011
# MAGIC 4. Evolução das vendas no tempo
# MAGIC 5. Ticket médio e o efeito de mix entre canais
# MAGIC 6. Canais de venda
# MAGIC 7. Produtos e categorias
# MAGIC 8. Onde vendemos
# MAGIC 9. Clientes
# MAGIC 10. Motivos de venda e o efeito da promoção
# MAGIC 11. Formas de pagamento
# MAGIC 12. Conclusões e implicações para o dashboard

# COMMAND ----------

# Setup: libraries, table names, chart style and helpers shared by every cell.
from decimal import Decimal

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

CATALOG = "workspace"
RAW = f"{CATALOG}.adventure_works"  # source tables (raw copy of the OLTP database)
MARTS = f"{CATALOG}.dev_cea_aw_marts"  # dimensional model built by dbt

# Same palette as the dashboard theme
TEAL, BLUE, ORANGE, PURPLE, YELLOW, PINK, GREEN, GRAY = [
    "#2A9D8F", "#5B8FD9", "#E76F51", "#9C7BD1", "#E9C46A", "#D45D8C", "#8AB17D", "#7A8B99",
]
CANAL_CORES = {"Online": TEAL, "Revenda (lojas)": BLUE}
CANAL_SQL = "CASE WHEN f.flag_pedido_online THEN 'Online' ELSE 'Revenda (lojas)' END"

plt.rcParams.update({
    "figure.dpi": 110,
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "legend.frameon": False,
})


def q(sql: str) -> pd.DataFrame:
    """Run a read-only query and return a pandas DataFrame.

    Spark turns DECIMAL columns into Python Decimal objects, which pandas and matplotlib handle
    poorly, so every money column used in a chart is cast to DOUBLE in the SQL.
    """
    return spark.sql(sql).toPandas()


def br(valor, casas=0):
    """Format a number in Brazilian style (1.234.567,89)."""
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def pct(valor, casas=1):
    """Format a 0-1 share as a Brazilian percentage (12,3%)."""
    return f"{br(100 * float(valor), casas)}%"


milhoes = mticker.FuncFormatter(lambda v, _: br(v / 1e6, 0))
milhares = mticker.FuncFormatter(lambda v, _: br(v / 1e3, 0))
inteiro = mticker.FuncFormatter(lambda v, _: br(v, 0))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Inventário das tabelas de origem
# MAGIC Quantas linhas tem cada uma das 18 tabelas usadas pelo modelo dbt.

# COMMAND ----------

tabelas = {
    "salesorderheader": "Cabeçalho do pedido (1 linha por pedido)",
    "salesorderdetail": "Itens do pedido (1 linha por produto no pedido)",
    "customer": "Clientes (pessoas e lojas)",
    "person": "Pessoas (nomes)",
    "businessentityaddress": "Ligação pessoa ou loja → endereço",
    "address": "Endereços",
    "stateprovince": "Estados / províncias",
    "countryregion": "Países",
    "salesterritory": "Territórios de venda",
    "product": "Produtos",
    "productsubcategory": "Subcategorias de produto",
    "productcategory": "Categorias de produto",
    "specialoffer": "Ofertas especiais (descontos)",
    "salesreason": "Motivos de venda",
    "salesorderheadersalesreason": "Pedido × motivo de venda",
    "creditcard": "Cartões de crédito",
    "personcreditcard": "Pessoa × cartão de crédito",
    "shipmethod": "Métodos de envio",
}
inventario = q(" UNION ALL ".join(
    f"SELECT '{tabela}' AS tabela, COUNT(*) AS linhas FROM {RAW}.{tabela}" for tabela in tabelas
))
inventario["conteudo"] = inventario["tabela"].map(tabelas)
display(inventario)

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - A base tem 31.465 pedidos com 121.317 itens (3,9 itens por pedido em média), 19.820 clientes e 504 produtos.
# MAGIC - `person` (19.972) é maior que `customer` porque guarda todas as pessoas do sistema, não só clientes.
# MAGIC - `creditcard` e `personcreditcard` têm o mesmo tamanho (19.118): cada cartão pertence a uma única pessoa.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Qualidade dos dados
# MAGIC Chaves, nulos e consistência entre as tabelas brutas. Cada verificação explica uma regra aplicada no modelo.

# COMMAND ----------

pedidos_sem_motivo = f"""
    SELECT COUNT(*) FROM {RAW}.salesorderheader h
    LEFT ANTI JOIN {RAW}.salesorderheadersalesreason r ON r.salesorderid = h.salesorderid
    WHERE CAST(h.onlineorderflag AS BOOLEAN) = {{online}}
"""
qualidade = q(f"""
SELECT
  (SELECT COUNT(*) FROM {RAW}.salesorderheader) AS pedidos,
  (SELECT COUNT(DISTINCT salesorderid) FROM {RAW}.salesorderheader) AS pedidos_distintos,
  (SELECT COUNT(*) FROM {RAW}.salesorderdetail) AS linhas,
  (SELECT COUNT(DISTINCT salesorderdetailid) FROM {RAW}.salesorderdetail) AS linhas_distintas,
  (SELECT COUNT(DISTINCT salesorderid, productid) FROM {RAW}.salesorderdetail) AS pedido_produto_distintos,
  (SELECT COUNT(*) FROM {RAW}.salesorderdetail d
     LEFT ANTI JOIN {RAW}.salesorderheader h ON h.salesorderid = d.salesorderid) AS linhas_orfas,
  (SELECT COUNT(*) FROM {RAW}.salesorderheader WHERE creditcardid IS NULL) AS pedidos_sem_cartao,
  (SELECT COUNT(*) FROM {RAW}.salesorderheader WHERE NOT CAST(onlineorderflag AS BOOLEAN)) AS pedidos_revenda,
  ({pedidos_sem_motivo.format(online="true")}) AS online_sem_motivo,
  ({pedidos_sem_motivo.format(online="false")}) AS revenda_sem_motivo,
  (SELECT COUNT(DISTINCT status) FROM {RAW}.salesorderheader) AS status_distintos,
  (SELECT COUNT(*) FROM {RAW}.salesorderheader h
     LEFT ANTI JOIN {RAW}.address a ON a.addressid = h.shiptoaddressid) AS pedidos_sem_endereco_entrega,
  (SELECT COUNT(*) FROM {RAW}.product) AS produtos,
  (SELECT COUNT(DISTINCT productid) FROM {RAW}.salesorderdetail) AS produtos_vendidos,
  (SELECT COUNT(*) FROM {RAW}.customer) AS clientes,
  (SELECT COUNT(DISTINCT customerid) FROM {RAW}.salesorderheader) AS clientes_com_pedido,
  (SELECT MIN(CAST(orderdate AS DATE)) FROM {RAW}.salesorderheader) AS primeira_data,
  (SELECT MAX(CAST(orderdate AS DATE)) FROM {RAW}.salesorderheader) AS ultima_data
""").iloc[0]

# Share of the value whose customer has no personal address (the reason location comes from the order)
sem_endereco_cliente = q(f"""
SELECT CAST(SUM(CASE WHEN a.businessentityid IS NULL THEN d.unitprice * d.orderqty ELSE 0 END)
          / SUM(d.unitprice * d.orderqty) AS DOUBLE) AS pct
FROM {RAW}.salesorderdetail d
JOIN {RAW}.salesorderheader h ON h.salesorderid = d.salesorderid
JOIN {RAW}.customer c ON c.customerid = h.customerid
LEFT JOIN (SELECT DISTINCT businessentityid FROM {RAW}.businessentityaddress) a ON a.businessentityid = c.personid
""").iloc[0]["pct"]

# The order header subtotal must equal the sum of its net lines (price x quantity x (1 - discount))
conciliacao = q(f"""
SELECT
  SUM(CASE WHEN ABS(h.subtotal - l.liquido) > 0.01 THEN 1 ELSE 0 END) AS pedidos_divergentes,
  CAST(SUM(h.subtotal) AS DOUBLE) AS soma_subtotal,
  CAST(SUM(l.liquido) AS DOUBLE) AS soma_linhas
FROM (SELECT salesorderid, CAST(subtotal AS DECIMAL(18, 2)) AS subtotal FROM {RAW}.salesorderheader) h
JOIN (
  SELECT salesorderid,
    SUM(CAST(unitprice AS DECIMAL(18, 4)) * orderqty * (1 - CAST(unitpricediscount AS DECIMAL(18, 4)))) AS liquido
  FROM {RAW}.salesorderdetail GROUP BY salesorderid
) l ON l.salesorderid = h.salesorderid
""").iloc[0]

r = qualidade
verificacoes = pd.DataFrame([
    ("Número do pedido é único no cabeçalho", f"{br(r.pedidos_distintos)} distintos em {br(r.pedidos)}",
     r.pedidos == r.pedidos_distintos),
    ("Item do pedido é único", f"{br(r.linhas_distintas)} distintos em {br(r.linhas)}", r.linhas == r.linhas_distintas),
    ("Pedido × produto é único (cada produto aparece uma vez por pedido)",
     f"{br(r.pedido_produto_distintos)} combinações em {br(r.linhas)} itens", r.pedido_produto_distintos == r.linhas),
    ("Itens sem cabeçalho de pedido", br(r.linhas_orfas), r.linhas_orfas == 0),
    ("Pedidos sem endereço de entrega válido", br(r.pedidos_sem_endereco_entrega), r.pedidos_sem_endereco_entrega == 0),
    ("Subtotal do cabeçalho = soma dos itens líquidos", f"{br(conciliacao.pedidos_divergentes)} pedidos divergentes "
     f"(total US$ {br(conciliacao.soma_subtotal, 2)} vs US$ {br(conciliacao.soma_linhas, 2)})",
     conciliacao.pedidos_divergentes == 0),
    ("Pedidos sem cartão de crédito", f"{br(r.pedidos_sem_cartao)} ({pct(r.pedidos_sem_cartao / r.pedidos)})", False),
    ("Pedidos online sem motivo de venda", br(r.online_sem_motivo), False),
    ("Pedidos de revenda sem motivo de venda", f"{br(r.revenda_sem_motivo)} de {br(r.pedidos_revenda)}", False),
    ("Status distintos nos pedidos", br(r.status_distintos), False),
    ("Valor de clientes sem endereço próprio", pct(sem_endereco_cliente), False),
    ("Produtos com venda", f"{br(r.produtos_vendidos)} de {br(r.produtos)}", False),
    ("Clientes com pedido", f"{br(r.clientes_com_pedido)} de {br(r.clientes)}", False),
    ("Período dos pedidos", f"{r.primeira_data} a {r.ultima_data}", True),
], columns=["verificacao", "resultado", "ok"])
verificacoes["situacao"] = np.where(verificacoes["ok"], "OK", "Ponto de atenção")
display(verificacoes.drop(columns="ok"))

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights e regras aplicadas no modelo**
# MAGIC - **Chaves íntegras:** pedido, item e a combinação pedido × produto são únicos, não há item sem pedido e o subtotal de cada pedido bate com a soma dos seus itens (no total, a diferença é de centavos de arredondamento). Por isso o grão da fato é o item do pedido, e o número do pedido fica na fato como dimensão degenerada (`fk_pedido_venda`).
# MAGIC - **1.131 pedidos sem cartão** (1.124 online e 7 de revenda) recebem `N/A` como tipo de cartão, para não aparecerem como vazio nos gráficos e filtros.
# MAGIC - **Motivo de venda só existe no online:** nenhum dos 3.806 pedidos de revenda tem motivo, e 4.647 pedidos online também não. Esses pedidos recebem `Nenhum`. Toda análise de motivo de venda fala apenas do canal online.
# MAGIC - **Status único:** todos os pedidos estão com status 5 (Enviado). O gráfico de status do dashboard é uma fatia só: o indicador foi pedido no desafio, mas não discrimina nada nesta base.
# MAGIC - **73,4% do valor vem de clientes sem endereço próprio** (as lojas). Se a cidade viesse do cadastro do cliente, quase três quartos do faturamento ficariam sem localização. Por isso a localização vem do **endereço de entrega do pedido**, presente em 100% dos pedidos.
# MAGIC - **238 dos 504 produtos nunca foram vendidos** e 701 clientes não têm pedido. As dimensões guardam o cadastro completo, mas os rankings só mostram quem vendeu ou comprou.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Auditoria contábil: vendas brutas de 2011
# MAGIC O valor de referência é **US$ 12.646.112,16**. A conta é feita direto na origem e no modelo, e também com o preço arredondado para 2 casas, para medir o efeito da precisão.

# COMMAND ----------

REFERENCIA_2011 = Decimal("12646112.16")
auditoria = q(f"""
SELECT
  (SELECT ROUND(SUM(CAST(d.unitprice AS DECIMAL(18, 4)) * CAST(d.orderqty AS INT)), 2)
     FROM {RAW}.salesorderdetail d JOIN {RAW}.salesorderheader h ON h.salesorderid = d.salesorderid
     WHERE YEAR(CAST(h.orderdate AS DATE)) = 2011) AS origem,
  (SELECT ROUND(SUM(valor_bruto_linha), 2) FROM {MARTS}.fct_pedidos_vendas WHERE YEAR(data_pedido) = 2011) AS modelo,
  (SELECT ROUND(SUM(ROUND(CAST(d.unitprice AS DECIMAL(18, 4)), 2) * CAST(d.orderqty AS INT)), 2)
     FROM {RAW}.salesorderdetail d JOIN {RAW}.salesorderheader h ON h.salesorderid = d.salesorderid
     WHERE YEAR(CAST(h.orderdate AS DATE)) = 2011) AS preco_arredondado
""").iloc[0]
for nome, valor in auditoria.items():
    diferenca = Decimal(valor) - REFERENCIA_2011
    print(f"{nome:<18} US$ {br(valor, 2):>17}   diferença: US$ {br(diferenca, 2)}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Insight:** a soma bruta de 2011 (preço unitário × quantidade, antes dos descontos) bate **exatamente** com o valor de referência, tanto na origem quanto no modelo. Com o preço arredondado para 2 casas, o total erra em US$ 6,58. Por isso o staging mantém o preço em `decimal(18,4)`, e o teste dbt `assert_gross_sales_2011` compara com o valor exato, sem margem de tolerância.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Evolução das vendas no tempo

# COMMAND ----------

mensal = q(f"""
SELECT date_format(f.data_pedido, 'yyyy-MM') AS mes, {CANAL_SQL} AS canal,
  COUNT(DISTINCT f.fk_pedido_venda) AS pedidos,
  CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto,
  CAST(SUM(f.quantidade) AS BIGINT) AS quantidade
FROM {MARTS}.fct_pedidos_vendas f
GROUP BY ALL ORDER BY mes, canal
""")
# Months without reseller orders have no row for that channel: pivot and fill them with zero
painel = mensal.pivot_table(index="mes", columns="canal", values=["pedidos", "valor_bruto", "quantidade"],
                            aggfunc="sum", fill_value=0)
meses = painel.index.tolist()
x = np.arange(len(meses))
parciais = [meses.index(m) for m in ("2011-05", "2014-06")]  # first day only / atypical last month

fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
for ax, (medida, titulo, formato, rotulo) in zip(axes, [
    ("valor_bruto", "Valor total negociado por mês", milhoes, "US$ milhões"),
    ("pedidos", "Número de pedidos por mês", inteiro, "pedidos"),
    ("quantidade", "Quantidade comprada por mês", milhares, "mil unidades"),
]):
    base = np.zeros(len(meses))
    for canal in ["Revenda (lojas)", "Online"]:
        valores = painel[(medida, canal)].to_numpy()
        ax.bar(x, valores, bottom=base, color=CANAL_CORES[canal], label=canal, width=0.8)
        base += valores
    for i in parciais:
        ax.axvspan(i - 0.5, i + 0.5, color=GRAY, alpha=0.18, lw=0)
    ax.set_title(titulo, loc="left")
    ax.set_ylabel(rotulo)
    ax.yaxis.set_major_formatter(formato)
axes[0].legend(loc="upper left")
axes[-1].set_xticks(x[::3], meses[::3], rotation=45)
fig.text(0.01, 0.005, "Faixas cinza: maio/2011 (só o dia 31) e junho/2014 (mês atípico, sem revenda e sem bicicletas).",
         fontsize=9, color=GRAY)
fig.tight_layout()
plt.show()

anual = q(f"""
SELECT YEAR(f.data_pedido) AS ano, COUNT(DISTINCT date_format(f.data_pedido, 'yyyy-MM')) AS meses,
  COUNT(DISTINCT f.fk_pedido_venda) AS pedidos, CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto,
  CAST(SUM(f.valor_total_linha) AS DOUBLE) AS valor_liquido, CAST(SUM(f.quantidade) AS BIGINT) AS quantidade
FROM {MARTS}.fct_pedidos_vendas f GROUP BY ALL ORDER BY ano
""")
anual["valor_bruto_por_mes"] = anual["valor_bruto"] / anual["meses"]
display(anual)

# Like-for-like comparison: same months (January to May) in 2013 and 2014
jan_mai = mensal[mensal["mes"].str[5:].between("01", "05")].assign(ano=lambda d: d["mes"].str[:4])
jan_mai = jan_mai[jan_mai["ano"].isin(["2013", "2014"])].groupby("ano")[["pedidos", "valor_bruto"]].sum()
print("Janeiro a maio:", {ano: f"{br(v.pedidos)} pedidos, US$ {br(v.valor_bruto / 1e6, 1)} mi" for ano, v in jan_mai.iterrows()})
print(f"Variação 2014 vs 2013 (jan-mai): pedidos {pct(jan_mai.pedidos['2014'] / jan_mai.pedidos['2013'] - 1)}, "
      f"valor {pct(jan_mai.valor_bruto['2014'] / jan_mai.valor_bruto['2013'] - 1)}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **O negócio cresceu, mas 2014 está incompleto.** O valor total negociado foi de US$ 12,6 mi em 2011 (8 meses) para US$ 33,7 mi em 2012 e US$ 43,9 mi em 2013. 2014 tem só 6 meses (US$ 20,1 mi). Comparar o ano de 2014 com 2013 inteiro sugere uma queda que não existe: de janeiro a maio, 2014 vendeu **46,7% mais** que o mesmo período de 2013 (US$ 20,0 mi contra US$ 13,7 mi).
# MAGIC - **Pedidos e valor contam histórias diferentes.** Entre 2012 e 2013 os pedidos quase quadruplicaram (3.915 para 14.182, +262%), mas o valor subiu só 30%. De janeiro a maio de 2014, os pedidos cresceram 435% e o valor 46,7%. Os pedidos novos são do canal online, com ticket bem menor (seções 5 e 6). Por isso o dashboard mostra valor, pedidos, quantidade e ticket médio lado a lado: um sozinho engana.
# MAGIC - **A revenda (azul) concentra o valor e o online (verde) concentra os pedidos.** A partir de meados de 2013 o online passa a dominar os pedidos e a quantidade, mas a revenda continua sendo a maior parte do valor.
# MAGIC - **Meses de borda:** maio/2011 tem só o dia 31 e junho/2014 é atípico (só pedidos online de acessórios e roupas). Os dois ficam fora de qualquer comparação de tendência.

# COMMAND ----------

# Resellers place orders on a few dates: how are their orders spread over the days of the month?
calendario = q(f"""
SELECT day(f.data_pedido) AS dia, COUNT(DISTINCT f.fk_pedido_venda) AS pedidos
FROM {MARTS}.fct_pedidos_vendas f WHERE NOT f.flag_pedido_online GROUP BY ALL ORDER BY dia
""")
datas = q(f"""
SELECT {CANAL_SQL} AS canal, COUNT(DISTINCT CAST(f.data_pedido AS DATE)) AS datas_com_pedido,
  COUNT(DISTINCT date_format(f.data_pedido, 'yyyy-MM')) AS meses_com_pedido
FROM {MARTS}.fct_pedidos_vendas f GROUP BY ALL
""")
display(datas)

dias = calendario.set_index("dia").reindex(range(1, 32), fill_value=0)["pedidos"]
fig, ax = plt.subplots(figsize=(12, 3.6))
ax.bar(dias.index, dias.to_numpy(), color=BLUE)
ax.set_title("Pedidos de revenda por dia do mês", loc="left")
ax.set_xlabel("dia do mês")
ax.set_ylabel("pedidos")
ax.set_xticks(range(1, 32))
plt.show()
virada = dias.loc[[1, 28, 29, 30, 31]].sum() / dias.sum()
print(f"Pedidos de revenda feitos nos dias 1 e 28 a 31: {pct(virada)}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **As lojas compram uma vez por mês, na virada do mês.** Os pedidos de revenda aparecem em só 40 datas ao longo de 34 meses (o online tem pedidos em 1.124 datas), e 100% deles caem no dia 1 ou entre os dias 28 e 31. É um ciclo de reposição mensal, não uma demanda diária.
# MAGIC - **Consequência para a leitura da série:** se o fechamento cai no dia 1 do mês seguinte, um mês fica quase sem revenda e o seguinte bate recorde. Fevereiro/2014 teve só 3 pedidos de revenda e março/2014 foi o maior mês da série (cerca de US$ 7,2 mi). Por isso o dashboard trabalha com série **mensal** (não diária) e a variação de um mês isolado da revenda deve ser lida com cuidado: compare trimestres ou o acumulado do ano.

# COMMAND ----------

# The online channel changed in mid-2013: orders per product category and online ticket per month
online_cat = q(f"""
SELECT date_format(f.data_pedido, 'yyyy-MM') AS mes, p.nome_categoria AS categoria,
  COUNT(DISTINCT f.fk_pedido_venda) AS pedidos
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_produtos p ON p.pk_produto = f.fk_produto
WHERE f.flag_pedido_online GROUP BY ALL ORDER BY mes
""").pivot_table(index="mes", columns="categoria", values="pedidos", fill_value=0)
online_ticket = q(f"""
SELECT date_format(f.data_pedido, 'yyyy-MM') AS mes,
  CAST(SUM(f.valor_total_linha) / COUNT(DISTINCT f.fk_pedido_venda) AS DOUBLE) AS ticket
FROM {MARTS}.fct_pedidos_vendas f WHERE f.flag_pedido_online GROUP BY ALL ORDER BY mes
""").set_index("mes")["ticket"]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
xo = np.arange(len(online_cat.index))
for categoria, cor in zip(["Bikes", "Accessories", "Clothing"], [TEAL, ORANGE, PURPLE]):
    ax1.plot(xo, online_cat[categoria].to_numpy(), color=cor, lw=2, label=categoria)
ax1.set_title("Pedidos online que contêm cada categoria, por mês", loc="left")
ax1.set_ylabel("pedidos")
ax1.legend(loc="upper left")
ax2.plot(xo, online_ticket.reindex(online_cat.index).to_numpy(), color=TEAL, lw=2)
ax2.set_title("Ticket médio online por mês", loc="left")
ax2.set_ylabel("US$ por pedido")
ax2.yaxis.set_major_formatter(inteiro)
ax2.set_xticks(xo[::3], online_cat.index[::3], rotation=45)
fig.tight_layout()
plt.show()
display(online_cat.loc[["2012-05", "2012-06", "2013-04", "2013-05", "2013-06", "2013-07", "2014-05", "2014-06"]])

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **Até maio/2013 o canal online vendia só bicicletas.** Acessórios e roupas aparecem no fim de maio/2013 e decolam em junho e julho: em julho/2013 já são 1.309 pedidos com acessórios e 518 com roupas, contra 497 com bicicleta.
# MAGIC - **O ticket online cai em dois degraus**, e nenhum deles é perda de cliente: em junho/2012 (de cerca de US$ 3,2 mil para US$ 2,0 mil, troca de modelos de bicicleta, ver a próxima célula) e em julho/2013 (para a faixa de US$ 550 a 850, com a entrada de acessórios e roupas, de preço baixo).
# MAGIC - **Junho/2014 é atípico:** 939 pedidos online, nenhum com bicicleta e nenhum de revenda, somando cerca de US$ 49 mil. Parece um mês com carga incompleta e não deve ser usado como tendência.

# COMMAND ----------

# Online bike prices dropped twice: which models entered and left the online catalog?
bikes_online = q(f"""
SELECT date_format(f.data_pedido, 'yyyy-MM') AS mes,
  COUNT(DISTINCT f.fk_pedido_venda) AS pedidos_com_bicicleta,
  CAST(SUM(f.valor_bruto_linha) / SUM(f.quantidade) AS DOUBLE) AS preco_medio_bicicleta
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_produtos p ON p.pk_produto = f.fk_produto
WHERE f.flag_pedido_online AND p.nome_categoria = 'Bikes'
GROUP BY ALL ORDER BY mes
""").set_index("mes")
# Model = product name without color and size (e.g. "Mountain-200 Black, 38" -> "Mountain-200")
modelos = q(f"""
SELECT regexp_extract(p.nome_produto, '^([A-Za-z]+-[0-9]+(-W)?)', 1) AS modelo,
  MIN(date_format(f.data_pedido, 'yyyy-MM')) AS primeiro_mes, MAX(date_format(f.data_pedido, 'yyyy-MM')) AS ultimo_mes,
  CAST(MIN(f.preco_unitario) AS DOUBLE) AS preco_min, CAST(MAX(f.preco_unitario) AS DOUBLE) AS preco_max,
  CAST(SUM(f.quantidade) AS BIGINT) AS unidades
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_produtos p ON p.pk_produto = f.fk_produto
WHERE f.flag_pedido_online AND p.nome_categoria = 'Bikes'
GROUP BY ALL ORDER BY primeiro_mes, modelo
""")

meses_b = bikes_online.index.tolist()
xb = np.arange(len(meses_b))
fig, ax = plt.subplots(figsize=(13, 4.2))
ax.bar(xb, bikes_online["pedidos_com_bicicleta"], color=TEAL, alpha=0.35, label="Pedidos com bicicleta")
ax.set_ylabel("pedidos")
preco = ax.twinx()
preco.plot(xb, bikes_online["preco_medio_bicicleta"], color=ORANGE, lw=2, marker="o", ms=3, label="Preço médio da bicicleta")
preco.set_ylim(0, bikes_online["preco_medio_bicicleta"].max() * 1.25)
preco.set_ylabel("US$ por bicicleta")
preco.yaxis.set_major_formatter(inteiro)
preco.grid(False)
# Dashed lines: months in which new bike models started selling online
entradas = sorted(modelos.loc[modelos["primeiro_mes"] > modelos["primeiro_mes"].min(), "primeiro_mes"].unique())
for mes in entradas:
    ax.axvline(meses_b.index(mes), color=GRAY, ls="--", lw=1)
handles = (ax.get_legend_handles_labels()[0] + preco.get_legend_handles_labels()[0]
           + [Line2D([], [], color=GRAY, ls="--", lw=1, label="Entrada de modelos novos")])
preco.legend(handles=handles, loc="center left")
ax.set_xticks(xb[::3], meses_b[::3], rotation=45)
ax.set_title("Bicicletas no canal online: pedidos (barras) e preço médio por unidade (linha)", loc="left")
fig.tight_layout()
plt.show()
display(modelos)

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **Maio/2012: troca de geração.** Saem os modelos mais caros (Mountain-100, cerca de US$ 3.400, e Road-150, US$ 3.578) e entram Mountain-200 (US$ 2.049 a 2.320), Road-250 (US$ 2.182 a 2.443) e Road-550-W (US$ 1.000 a 1.120). O preço médio da bicicleta vendida online cai de cerca de US$ 3.100 para US$ 2.000, e os pedidos com bicicleta sobem (de 221 em maio para 251 em junho e 274 em julho).
# MAGIC - **Maio e junho/2013: entrada da linha de entrada.** Seis modelos chegam em maio (Road-750 a US$ 540, Touring-3000 a US$ 742, Mountain-400-W a US$ 769, Touring-2000, Road-350-W e Touring-1000) e a Mountain-500 (US$ 540 a 565) em junho. A Road-650 sai em maio/2013. O preço médio cai de novo, para cerca de US$ 1.600, e os pedidos com bicicleta crescem até 1.186 em maio/2014.
# MAGIC - **Leitura para o negócio:** a queda do ticket médio online é decisão de portfólio (bicicletas mais baratas e categorias novas), acompanhada de mais volume. O ticket médio deve ser lido junto com o mix de produtos, nunca sozinho.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Ticket médio e o efeito de mix entre canais

# COMMAND ----------

ticket_ano = q(f"""
SELECT YEAR(f.data_pedido) AS ano, 'Geral' AS grupo, COUNT(DISTINCT f.fk_pedido_venda) AS pedidos,
  CAST(SUM(f.valor_total_linha) / COUNT(DISTINCT f.fk_pedido_venda) AS DOUBLE) AS ticket
FROM {MARTS}.fct_pedidos_vendas f GROUP BY ALL
UNION ALL
SELECT YEAR(f.data_pedido), {CANAL_SQL}, COUNT(DISTINCT f.fk_pedido_venda),
  CAST(SUM(f.valor_total_linha) / COUNT(DISTINCT f.fk_pedido_venda) AS DOUBLE)
FROM {MARTS}.fct_pedidos_vendas f GROUP BY ALL
""")
tabela_ticket = ticket_ano.pivot_table(index="ano", columns="grupo", values="ticket")
pedidos_ano = ticket_ano.pivot_table(index="ano", columns="grupo", values="pedidos")
share_online = pedidos_ano["Online"] / pedidos_ano["Geral"]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.2), gridspec_kw={"width_ratios": [2, 1]})
anos = tabela_ticket.index.to_numpy()
largura = 0.27
for deslocamento, (grupo, cor) in zip([-1, 0, 1], [("Geral", GRAY), ("Online", TEAL), ("Revenda (lojas)", BLUE)]):
    barras = ax1.bar(anos + deslocamento * largura, tabela_ticket[grupo], largura, color=cor, label=grupo)
    ax1.bar_label(barras, labels=[br(v) for v in tabela_ticket[grupo]], fontsize=8, padding=2)
ax1.set_title("Ticket médio por ano (US$)", loc="left")
ax1.set_xticks(anos)
ax1.yaxis.set_major_formatter(inteiro)
ax1.set_ylim(0, tabela_ticket.max().max() * 1.18)
ax1.legend(loc="upper center", ncol=3)
barras = ax2.bar(anos, share_online * 100, color=TEAL)
ax2.bar_label(barras, labels=[pct(v, 0) for v in share_online], fontsize=8, padding=2)
ax2.set_title("Pedidos online no total (%)", loc="left")
ax2.set_xticks(anos)
ax2.set_ylim(0, 100)
fig.tight_layout()
plt.show()
display(tabela_ticket.round(2))

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **O ticket geral cai mais do que o de qualquer canal.** De 2012 para 2014 o ticket médio geral foi de US$ 8.563 para US$ 1.705 (-80%), enquanto o da revenda caiu 20% (US$ 23.152 para US$ 18.548) e o do online 68% (US$ 2.330 para US$ 752).
# MAGIC - **É efeito de mix (paradoxo de Simpson):** o online, com ticket cerca de 20 vezes menor, passou de 70% para 95% dos pedidos. A média geral desce porque o peso do canal barato aumentou, não porque cada canal piorou na mesma proporção.
# MAGIC - **Implicação para o dashboard:** o ticket médio sempre precisa ser lido por canal. Por isso o filtro "Canal de venda" alcança todas as páginas e a página de análises avançadas compara os canais lado a lado.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Canais de venda

# COMMAND ----------

canais = q(f"""
SELECT {CANAL_SQL} AS canal, COUNT(DISTINCT f.fk_pedido_venda) AS pedidos, COUNT(DISTINCT f.fk_cliente) AS clientes,
  COUNT(*) AS itens, CAST(SUM(f.quantidade) AS BIGINT) AS quantidade,
  CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto, CAST(SUM(f.valor_desconto_linha) AS DOUBLE) AS descontos,
  CAST(SUM(f.valor_total_linha) AS DOUBLE) AS valor_liquido
FROM {MARTS}.fct_pedidos_vendas f GROUP BY ALL ORDER BY canal
""").set_index("canal")
canais["ticket_medio"] = canais["valor_liquido"] / canais["pedidos"]
canais["itens_por_pedido"] = canais["itens"] / canais["pedidos"]
canais["unidades_por_pedido"] = canais["quantidade"] / canais["pedidos"]
canais["pedidos_por_cliente"] = canais["pedidos"] / canais["clientes"]
display(canais.round(2).reset_index())

medidas = {"pedidos": "Pedidos", "clientes": "Clientes", "quantidade": "Quantidade",
           "valor_bruto": "Valor total negociado", "descontos": "Descontos"}
participacao = canais[list(medidas)] / canais[list(medidas)].sum()
fig, ax = plt.subplots(figsize=(11, 3.8))
y = np.arange(len(medidas))[::-1]
esquerda = np.zeros(len(medidas))
for canal in ["Online", "Revenda (lojas)"]:
    valores = participacao.loc[canal].to_numpy()
    ax.barh(y, valores, left=esquerda, color=CANAL_CORES[canal], label=canal, height=0.6)
    for yi, v, e in zip(y, valores, esquerda):
        if v >= 0.06:
            ax.text(e + v / 2, yi, pct(v, 0), ha="center", va="center", color="white", fontweight="bold")
    esquerda += valores
ax.set_yticks(y, list(medidas.values()))
ax.set_xlim(0, 1)
ax.xaxis.set_major_formatter(mticker.PercentFormatter(1))
ax.grid(False)
ax.set_title("Participação de cada canal", loc="left")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.32), ncol=2)
fig.tight_layout()
plt.show()

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **Dois negócios diferentes na mesma base.** O online tem 88% dos pedidos (27.659) e 97% dos clientes (18.484), mas só 27% do valor (US$ 29,4 mi). A revenda tem 12% dos pedidos (3.806) e 3% dos clientes (635 lojas), mas 73% do valor (US$ 81,0 mi).
# MAGIC - **Tamanho do pedido:** a revenda tem ticket médio de US$ 21.148 contra US$ 1.061 no online (cerca de 20 vezes). Um pedido de loja tem em média 16 itens e 56 unidades; um pedido online tem 2,2 itens, e toda linha online tem quantidade 1.
# MAGIC - **Recorrência:** cada loja fez em média 6 pedidos no período, contra 1,5 por cliente online.
# MAGIC - **Descontos só existem na revenda:** US$ 527.508, ou 0,65% do valor bruto da revenda. O online não tem nenhum desconto registrado.

# COMMAND ----------

# Distribution of the order value per channel (log scale: values go from a few dollars to six figures)
valor_pedido = q(f"""
SELECT {CANAL_SQL} AS canal, CAST(SUM(f.valor_total_linha) AS DOUBLE) AS valor
FROM {MARTS}.fct_pedidos_vendas f GROUP BY f.fk_pedido_venda, f.flag_pedido_online
""")
faixas = np.logspace(0, np.log10(valor_pedido["valor"].max()) + 0.05, 60)
fig, ax = plt.subplots(figsize=(12, 4))
for canal in ["Online", "Revenda (lojas)"]:
    ax.hist(valor_pedido.loc[valor_pedido["canal"] == canal, "valor"], bins=faixas, color=CANAL_CORES[canal],
            alpha=0.75, label=canal)
ax.set_xscale("log")
ax.xaxis.set_major_formatter(inteiro)
ax.set_title("Distribuição do valor líquido por pedido", loc="left")
ax.set_xlabel("US$ por pedido (escala logarítmica)")
ax.set_ylabel("pedidos")
ax.legend()
plt.show()
display(valor_pedido.groupby("canal")["valor"].describe(percentiles=[0.25, 0.5, 0.75, 0.9]).round(2).reset_index())

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **O pedido online tem duas formas.** A distribuição é bimodal: um grupo abaixo de US$ 200 (acessórios e roupas) e outro entre US$ 500 e US$ 3.600 (pedidos com bicicleta, com pico entre US$ 2.000 e 2.500). A mediana (US$ 595) fica longe da média (US$ 1.061): o ticket médio online descreve uma mistura, não um pedido típico.
# MAGIC - **A revenda tem cauda longa.** Mediana de US$ 8.257, média de US$ 21.148, 10% dos pedidos acima de US$ 57.007 e o maior pedido em US$ 163.930. Poucos pedidos grandes puxam a média para cima.
# MAGIC - O desafio pede ticket médio, e é ele que o dashboard mostra. A leitura correta vem com o filtro de canal (e de produto), que separa os grupos.

# COMMAND ----------

# Where do the discounts come from? Special offers with a discount actually applied on the line
ofertas = q(f"""
SELECT o.descricao_oferta AS oferta, CAST(o.percentual_desconto AS DOUBLE) AS percentual_desconto,
  {CANAL_SQL} AS canal, COUNT(*) AS itens,
  CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto, CAST(SUM(f.valor_desconto_linha) AS DOUBLE) AS desconto
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_ofertas_especiais o ON o.pk_oferta_especial = f.fk_oferta_especial
WHERE f.valor_desconto_linha > 0
GROUP BY ALL ORDER BY desconto DESC
""")
display(ofertas.round(4))
print(f"Descontos: US$ {br(ofertas['desconto'].sum(), 2)} = {pct(ofertas['desconto'].sum() / canais['valor_bruto'].sum(), 2)} "
      f"do valor total negociado; itens com desconto no online: {br(ofertas.loc[ofertas['canal'] == 'Online', 'itens'].sum())}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **Desconto é pouco relevante no total:** 0,48% do valor total negociado, todo ele em pedidos de revenda. Por isso "valor total negociado" (bruto) e "valor líquido" quase coincidem no dashboard.
# MAGIC - **As ofertas com mais desconto são queimas de estoque e promoções de modelo:** Touring-1000 Promotion (20%), Mountain-100 Clearance Sale (35%, justamente o modelo que saiu do catálogo online em maio/2012) e Touring-3000 Promotion (15%), seguidas dos descontos por volume.
# MAGIC - **As ofertas especiais são a forma estruturada de registrar promoção** (desconto, período, produto). Isso contrasta com o motivo "On Promotion" do online, que não tem nenhum desconto associado (seção 10).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Produtos e categorias

# COMMAND ----------

categorias = q(f"""
SELECT p.nome_categoria AS categoria, COUNT(DISTINCT f.fk_produto) AS produtos,
  CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto, CAST(SUM(f.quantidade) AS BIGINT) AS quantidade,
  CAST(SUM(CASE WHEN f.flag_pedido_online THEN f.valor_bruto_linha ELSE 0 END) AS DOUBLE) AS valor_online
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_produtos p ON p.pk_produto = f.fk_produto
GROUP BY ALL ORDER BY valor_bruto DESC
""").set_index("categoria")
categorias["pct_valor"] = categorias["valor_bruto"] / categorias["valor_bruto"].sum()
categorias["pct_quantidade"] = categorias["quantidade"] / categorias["quantidade"].sum()
categorias["pct_valor_online"] = categorias["valor_online"] / categorias["valor_bruto"]
categorias["preco_medio"] = categorias["valor_bruto"] / categorias["quantidade"]
display(categorias.round(4).reset_index())

fig, ax = plt.subplots(figsize=(11, 4))
y = np.arange(len(categorias))[::-1]
for deslocamento, (coluna, nome, cor) in zip([0.2, -0.2], [("pct_valor", "Valor total negociado", TEAL),
                                                            ("pct_quantidade", "Quantidade", ORANGE)]):
    barras = ax.barh(y + deslocamento, categorias[coluna], 0.4, color=cor, label=nome)
    ax.bar_label(barras, labels=[pct(v) for v in categorias[coluna]], fontsize=8, padding=3)
ax.set_yticks(y, categorias.index)
ax.xaxis.set_major_formatter(mticker.PercentFormatter(1))
ax.set_xlim(0, 1)
ax.set_title("Participação de cada categoria no valor e na quantidade", loc="left")
ax.legend(loc="lower right")
plt.show()

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **Bicicletas são o negócio:** 86,2% do valor com 32,8% das unidades. Componentes vêm a seguir com 10,7% do valor e são vendidos só na revenda (0% online).
# MAGIC - **Roupas e acessórios são volume, não valor:** juntos somam 49,3% das unidades e só 3,1% do valor (preço médio de US$ 29 e US$ 21). Os acessórios são a categoria mais "online": 54,8% do seu valor vem desse canal.
# MAGIC - **Implicação:** "mais vendido" depende da métrica. O dashboard mostra o ranking por valor e deixa claro quando a pergunta é por quantidade (como no produto mais vendido sob o motivo Promotion).

# COMMAND ----------

# Pareto / ABC of products: same rule as the dashboard (A up to 80% of the value, B up to 95%, C the rest)
produtos = q(f"""
SELECT p.nome_produto AS produto, p.nome_categoria AS categoria,
  CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto, CAST(SUM(f.quantidade) AS BIGINT) AS quantidade
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_produtos p ON p.pk_produto = f.fk_produto
GROUP BY ALL
""").sort_values(["valor_bruto", "produto"], ascending=[False, True]).reset_index(drop=True)
produtos["participacao"] = produtos["valor_bruto"] / produtos["valor_bruto"].sum()
produtos["pct_acumulado"] = produtos["participacao"].cumsum()
produtos["classe"] = np.select([produtos["pct_acumulado"] <= 0.80, produtos["pct_acumulado"] <= 0.95], ["A", "B"], "C")

abc = produtos.groupby("classe").agg(produtos=("produto", "count"), valor_bruto=("valor_bruto", "sum"))
abc["pct_produtos"] = abc["produtos"] / abc["produtos"].sum()
abc["pct_valor"] = abc["valor_bruto"] / abc["valor_bruto"].sum()
display(abc.round(4).reset_index())

cores_classe = produtos["classe"].map({"A": TEAL, "B": YELLOW, "C": GRAY}).tolist()
fig, ax = plt.subplots(figsize=(13, 4.5))
posicoes = np.arange(1, len(produtos) + 1)
ax.bar(posicoes, produtos["participacao"] * 100, color=cores_classe, width=1.0)
ax.set_ylabel("% do valor (cada produto)")
ax.set_xlabel("produtos ordenados do maior para o menor valor")
linha = ax.twinx()
linha.plot(posicoes, produtos["pct_acumulado"] * 100, color=ORANGE, lw=2)
linha.axhline(80, color=ORANGE, ls="--", lw=1)
linha.set_ylim(0, 102)
linha.set_ylabel("% acumulado do valor")
linha.grid(False)
n_a = int(abc.loc["A", "produtos"])
linha.annotate(f"{n_a} produtos (classe A) = 80% do valor", xy=(n_a, 80), xytext=(n_a + 25, 55),
               arrowprops={"arrowstyle": "->", "color": ORANGE}, color=ORANGE)
ax.set_title("Pareto de produtos: participação individual (barras) e acumulada (linha)", loc="left")
linha.legend(handles=[Patch(color=TEAL, label="Classe A (até 80% do valor)"),
                      Patch(color=YELLOW, label="Classe B (80% a 95%)"),
                      Patch(color=GRAY, label="Classe C (últimos 5%)"),
                      linha.get_lines()[0]],
             labels=["Classe A (até 80% do valor)", "Classe B (80% a 95%)", "Classe C (últimos 5%)", "% acumulado"],
             loc="center right")
plt.show()

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **Concentração forte, perto do 80/20:** 63 dos 266 produtos vendidos (23,7%) somam 79,85% do valor (classe A). A classe B tem 66 produtos (24,8%) e 15,1% do valor. A classe C tem **137 produtos, mais da metade do portfólio vendido, e só 5,1% do valor**.
# MAGIC - Nenhum produto isolado domina: o maior tem cerca de 4% do valor. O risco está em grupos de produtos (as bicicletas Mountain-200 e Road-250), não em um item.
# MAGIC - **Ação:** a classe A pede prioridade de estoque e disponibilidade. A classe C é candidata a revisão de sortimento (custo de manter o item contra o que ele vende). A mesma regra A/B/C está na página "Análises avançadas" do dashboard e responde aos filtros.

# COMMAND ----------

# Best sellers by value and by quantity are different products
top_valor = produtos.nlargest(10, "valor_bruto").iloc[::-1]
top_qtd = produtos.nlargest(10, "quantidade").iloc[::-1]
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4.8))
ax1.barh(top_valor["produto"], top_valor["valor_bruto"], color=TEAL)
ax1.xaxis.set_major_formatter(milhoes)
ax1.set_xlabel("US$ milhões")
ax1.set_title("Top 10 produtos por valor total negociado", loc="left")
ax2.barh(top_qtd["produto"], top_qtd["quantidade"], color=ORANGE)
ax2.xaxis.set_major_formatter(inteiro)
ax2.set_xlabel("unidades")
ax2.set_title("Top 10 produtos por quantidade", loc="left")
fig.tight_layout()
plt.show()
display(top_qtd.iloc[::-1][["produto", "categoria", "quantidade", "valor_bruto"]])

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **Os dois rankings não têm nenhum produto em comum.** Por valor, o Top 10 é só de bicicletas Mountain-200, Road-250 e Road-150, com a Mountain-200 Black, 38 na liderança (cerca de US$ 4,4 mi). Por quantidade, não há nenhuma bicicleta: lideram o boné AWC Logo Cap (8.311 unidades), a garrafa Water Bottle - 30 oz. (6.815) e os capacetes Sport-100 (cerca de 6.300 a 6.700 cada).
# MAGIC - Os itens de volume são baratos e entram junto com a bicicleta. São bons candidatos a venda casada e a exposição no checkout online.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Onde vendemos
# MAGIC A localização vem do **endereço de entrega do pedido** (ver seção 2).

# COMMAND ----------

paises = q(f"""
SELECT l.pais, {CANAL_SQL} AS canal, COUNT(DISTINCT f.fk_pedido_venda) AS pedidos,
  CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto, CAST(SUM(f.valor_total_linha) AS DOUBLE) AS valor_liquido
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_localidades l ON l.pk_localidade = f.fk_localidade
GROUP BY ALL
""")
por_pais = paises.pivot_table(index="pais", columns="canal", values="valor_bruto", fill_value=0)
por_pais["total"] = por_pais.sum(axis=1)
por_pais = por_pais.sort_values("total")
resumo_pais = paises.groupby("pais")[["pedidos", "valor_bruto", "valor_liquido"]].sum()
resumo_pais["pct_valor"] = resumo_pais["valor_bruto"] / resumo_pais["valor_bruto"].sum()
resumo_pais["ticket_medio"] = resumo_pais["valor_liquido"] / resumo_pais["pedidos"]
resumo_pais["pct_valor_online"] = por_pais["Online"] / por_pais["total"]

fig, ax = plt.subplots(figsize=(11, 4))
esquerda = np.zeros(len(por_pais))
for canal in ["Revenda (lojas)", "Online"]:
    ax.barh(por_pais.index, por_pais[canal], left=esquerda, color=CANAL_CORES[canal], label=canal, height=0.6)
    esquerda += por_pais[canal].to_numpy()
for yi, (pais, total) in enumerate(por_pais["total"].items()):
    ax.text(total, yi, f"  {pct(resumo_pais.loc[pais, 'pct_valor'])}", va="center", fontsize=9)
ax.xaxis.set_major_formatter(milhoes)
ax.set_xlabel("US$ milhões")
ax.set_title("Valor total negociado por país (endereço de entrega)", loc="left")
ax.legend(loc="lower right")
plt.show()
display(resumo_pais.sort_values("valor_bruto", ascending=False).round(4).reset_index())

cidades = q(f"""
SELECT l.cidade, l.estado, l.pais, COUNT(DISTINCT f.fk_pedido_venda) AS pedidos,
  CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto,
  CAST(SUM(CASE WHEN f.flag_pedido_online THEN 0 ELSE f.valor_bruto_linha END) / SUM(f.valor_bruto_linha) AS DOUBLE)
    AS pct_valor_revenda
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_localidades l ON l.pk_localidade = f.fk_localidade
GROUP BY ALL ORDER BY valor_bruto DESC LIMIT 5
""")
display(cidades.round(4))

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **América do Norte é 72% do valor** (Estados Unidos 57,4% e Canadá 14,9%), e lá o negócio é quase todo revenda: o online responde por só 14,8% do valor nos EUA e 12,0% no Canadá.
# MAGIC - **A Austrália é o oposto:** 84,8% do seu valor vem do online e ela tem o menor ticket médio (US$ 1.557, contra US$ 5.232 nos EUA). Alemanha (58,5% online) e Reino Unido (44,0%) também têm peso online alto. A diferença de ticket entre países é, na maior parte, diferença de canal.
# MAGIC - **O ranking de cidades é o mapa das lojas:** Toronto lidera com US$ 4,5 mi em 176 pedidos, 100% revenda, enquanto Londres (2ª, US$ 2,8 mi) precisa de 756 pedidos para chegar lá. Seattle e Burnaby também são quase só revenda.
# MAGIC - Há cidades com o mesmo nome em estados diferentes, por isso o Top 5 do dashboard agrupa cidade, estado e país.

# COMMAND ----------

ticket_pais = q(f"""
SELECT YEAR(f.data_pedido) AS ano, l.pais,
  CAST(SUM(f.valor_total_linha) / COUNT(DISTINCT f.fk_pedido_venda) AS DOUBLE) AS ticket
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_localidades l ON l.pk_localidade = f.fk_localidade
GROUP BY ALL
""").pivot_table(index="ano", columns="pais", values="ticket")
fig, ax = plt.subplots(figsize=(11, 4.2))
for pais, cor in zip(ticket_pais.columns, [TEAL, BLUE, ORANGE, PURPLE, YELLOW, PINK]):
    ax.plot(ticket_pais.index, ticket_pais[pais], marker="o", color=cor, lw=2, label=pais)
ax.set_xticks(ticket_pais.index)
ax.yaxis.set_major_formatter(inteiro)
ax.set_ylabel("US$ por pedido")
ax.set_title("Ticket médio anual por país", loc="left")
ax.legend(ncol=3, loc="upper right")
plt.show()
display(ticket_pais.round(0))

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - O ticket médio cai em todos os países a partir de 2013, pelo mesmo efeito de mix da seção 5. A queda é maior onde a revenda pesava mais: Canadá de US$ 12.741 (2012) para US$ 1.519 (2014) e EUA de US$ 12.845 para US$ 2.194.
# MAGIC - A Austrália, já majoritariamente online, sai de um patamar baixo (US$ 3.309 em 2011) e chega a US$ 1.119 em 2014.
# MAGIC - O dashboard responde ao "ticket médio mensal/anual por localização" com o filtro de canal disponível, para que a comparação entre países não misture lojas com consumidores finais.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Clientes

# COMMAND ----------

clientes = q(f"""
SELECT f.fk_cliente, concat(coalesce(c.nome_cliente, 'Sem nome'), ' (', f.fk_cliente, ')') AS cliente,
  c.tipo_pessoa, MAX({CANAL_SQL}) AS canal, COUNT(DISTINCT f.fk_pedido_venda) AS pedidos,
  CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_clientes c ON c.pk_cliente = f.fk_cliente
GROUP BY ALL
""").sort_values(["valor_bruto", "cliente"], ascending=[False, True]).reset_index(drop=True)
clientes["participacao"] = clientes["valor_bruto"] / clientes["valor_bruto"].sum()
clientes["pct_acumulado"] = clientes["participacao"].cumsum()
# Deciles exactly like SQL NTILE(10): the first (n mod 10) groups get one extra customer
n = len(clientes)
tamanhos = [n // 10 + (1 if i < n % 10 else 0) for i in range(10)]
clientes["decil"] = np.repeat(np.arange(1, 11), tamanhos)

decis = clientes.groupby("decil").agg(clientes=("cliente", "count"), valor_bruto=("valor_bruto", "sum"))
decis["participacao"] = decis["valor_bruto"] / decis["valor_bruto"].sum()
decis["pct_acumulado"] = decis["participacao"].cumsum()
rotulos = ["top 10%"] + [f"{(d - 1) * 10}-{d * 10}%" for d in range(2, 11)]

fig, ax = plt.subplots(figsize=(12, 4.3))
barras = ax.bar(rotulos, decis["participacao"] * 100, color=TEAL, label="% do valor na faixa")
ax.bar_label(barras, labels=[pct(v) for v in decis["participacao"]], fontsize=8, padding=2)
ax.plot(rotulos, decis["pct_acumulado"] * 100, color=ORANGE, marker="o", lw=2, label="% acumulado")
ax.axhline(80, color=ORANGE, ls="--", lw=1)
ax.set_ylim(0, 105)
ax.set_ylabel("% do valor total negociado")
ax.set_xlabel("faixas de clientes (decis), do maior para o menor valor")
ax.set_title("Pareto de clientes por faixa de 10%", loc="left")
ax.legend(loc="center right")
plt.show()

classe_a = clientes[clientes["pct_acumulado"] <= 0.80]
print(f"Clientes que somam 80% do valor: {br(len(classe_a))} de {br(n)} ({pct(len(classe_a) / n)})")
print("Classe A por tipo de cliente:", classe_a["tipo_pessoa"].value_counts().to_dict())

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **Concentração extrema:** os 10% de clientes com maior valor (cerca de 1.912) concentram 81,7% do valor total negociado. A metade de baixo da base (os 5 últimos decis) soma menos de 1%.
# MAGIC - Só **1.589 dos 19.119 clientes (8,3%) somam 80% do valor**. Entre eles estão 494 lojas (SC), ou seja, 78% das 635 lojas que compraram, e 1.095 pessoas físicas (IN), só 6% dos clientes online.
# MAGIC - **Ação:** a carteira de lojas é a carteira de contas-chave da empresa e merece gestão dedicada (atendimento, prazo de entrega, renovação de mix).

# COMMAND ----------

# Recurrence: how many orders does each customer place over the whole history?
faixas_pedidos = pd.cut(clientes["pedidos"], bins=[0, 1, 2, 3, 5, 10, 100], labels=["1", "2", "3", "4-5", "6-10", "11+"])
recorrencia = (clientes.assign(faixa=faixas_pedidos)
               .pivot_table(index="faixa", columns="canal", values="cliente", aggfunc="count", fill_value=0, observed=False))
recorrencia_pct = recorrencia / recorrencia.sum()

fig, ax = plt.subplots(figsize=(11, 4))
xr = np.arange(len(recorrencia_pct))
for deslocamento, canal in zip([-0.2, 0.2], ["Online", "Revenda (lojas)"]):
    barras = ax.bar(xr + deslocamento, recorrencia_pct[canal] * 100, 0.4, color=CANAL_CORES[canal], label=canal)
    ax.bar_label(barras, labels=[pct(v, 0) for v in recorrencia_pct[canal]], fontsize=8, padding=2)
ax.set_xticks(xr, recorrencia_pct.index)
ax.set_xlabel("pedidos por cliente no período")
ax.set_ylabel("% dos clientes do canal")
ax.set_title("Recorrência: quantos pedidos cada cliente fez", loc="left")
ax.legend()
plt.show()
display(clientes.groupby("canal")["pedidos"].describe().round(2).reset_index())

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **O online compra uma vez e vai embora:** 63% dos clientes online fizeram um único pedido em três anos e 30% fizeram dois. A média é de 1,5 pedido por cliente.
# MAGIC - **As lojas são recorrentes:** 86% delas fizeram 4 pedidos ou mais (40% fizeram 4 ou 5, 34% de 6 a 10 e 12% mais de 10), com média de 6 pedidos.
# MAGIC - **Ação:** a maior alavanca de crescimento do online é a **recompra**. Com 18,5 mil clientes que já compraram, converter parte dos 63% de compra única (por exemplo, oferecendo acessórios a quem comprou bicicleta) tende a custar menos do que adquirir clientes novos.

# COMMAND ----------

top10_clientes = clientes.head(10)[["cliente", "tipo_pessoa", "pedidos", "valor_bruto", "participacao"]]
display(top10_clientes.round(4))
print(f"Top 10 clientes somam {pct(top10_clientes['participacao'].sum())} do valor total negociado")

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **Os 10 maiores clientes são todos lojas (SC)** e somam 7,2% do valor total negociado. O maior, Roger Harui (29818), comprou US$ 882 mil em 12 pedidos, 0,8% do total.
# MAGIC - A concentração está no **grupo** de lojas, não em um cliente específico: perder qualquer uma delas tem impacto limitado, mas perder o canal de revenda seria perder 73% do valor.
# MAGIC - Na revenda, o nome do cliente é o da pessoa de contato da loja. O dashboard mostra o nome junto com o código do cliente para evitar ambiguidade entre homônimos.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Motivos de venda e o efeito da promoção
# MAGIC Os motivos de venda só existem nos pedidos online (seção 2), então esta seção olha apenas para esse canal.

# COMMAND ----------

motivos = q(f"""
SELECT motivo, COUNT(DISTINCT f.fk_pedido_venda) AS pedidos, CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto
FROM {MARTS}.fct_pedidos_vendas f
LATERAL VIEW explode(split(f.motivos_venda, ', ')) m AS motivo
WHERE f.flag_pedido_online
GROUP BY ALL ORDER BY pedidos
""")
total_online = int(canais.loc["Online", "pedidos"])
motivos["pct_pedidos"] = motivos["pedidos"] / total_online
fig, ax = plt.subplots(figsize=(11, 4))
barras = ax.barh(motivos["motivo"], motivos["pct_pedidos"], color=[GRAY if m == "Nenhum" else TEAL for m in motivos["motivo"]])
ax.bar_label(barras, labels=[f"{pct(v)}  ({br(p)})" for v, p in zip(motivos["pct_pedidos"], motivos["pedidos"])],
             fontsize=8, padding=3)
ax.xaxis.set_major_formatter(mticker.PercentFormatter(1))
ax.set_xlim(0, 0.8)
ax.set_title("Motivos de venda citados nos pedidos online (um pedido pode citar vários)", loc="left")
plt.show()

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **Preço é o motivo dominante:** citado em 63,2% dos pedidos online (17.473). "On Promotion" aparece em 12,7% (3.515), e os demais motivos (fabricante, qualidade, avaliações, propaganda na TV) ficam entre 2,6% e 6,3%.
# MAGIC - 16,8% dos pedidos online (4.647) não têm motivo registrado e aparecem como "Nenhum".
# MAGIC - Um pedido pode citar mais de um motivo, então as barras somam mais de 100%. No dashboard, o gráfico por motivo usa um dataset próprio (uma linha por motivo) para não duplicar valores nos demais gráficos.

# COMMAND ----------

# Does the "On Promotion" reason raise the ticket? Compare orders with and without it, then only orders with a bike
promocao = q(f"""
WITH pedidos AS (
  SELECT f.fk_pedido_venda,
    MAX(CASE WHEN array_contains(split(f.motivos_venda, ', '), 'On Promotion') THEN 1 ELSE 0 END) AS promocao,
    MAX(CASE WHEN p.nome_categoria = 'Bikes' THEN 1 ELSE 0 END) AS tem_bicicleta,
    SUM(f.valor_total_linha) AS valor_liquido,
    SUM(f.valor_desconto_linha) AS desconto,
    SUM(f.quantidade) AS unidades
  FROM {MARTS}.fct_pedidos_vendas f
  JOIN {MARTS}.dim_produtos p ON p.pk_produto = f.fk_produto
  WHERE f.flag_pedido_online
  GROUP BY f.fk_pedido_venda
)
SELECT CASE WHEN promocao = 1 THEN 'Com motivo Promotion' ELSE 'Sem motivo Promotion' END AS grupo,
  COUNT(*) AS pedidos,
  CAST(AVG(valor_liquido) AS DOUBLE) AS ticket_medio,
  CAST(AVG(tem_bicicleta) AS DOUBLE) AS pct_com_bicicleta,
  CAST(AVG(CASE WHEN tem_bicicleta = 1 THEN valor_liquido END) AS DOUBLE) AS ticket_pedidos_com_bicicleta,
  CAST(SUM(desconto) AS DOUBLE) AS descontos,
  CAST(AVG(unidades) AS DOUBLE) AS unidades_por_pedido
FROM pedidos GROUP BY ALL ORDER BY grupo
""").set_index("grupo")
display(promocao.round(4).reset_index())

fig, ax = plt.subplots(figsize=(10, 4))
xp = np.arange(2)
for deslocamento, (coluna, nome, cor) in zip([-0.2, 0.2], [("ticket_medio", "Todos os pedidos online", TEAL),
                                                            ("ticket_pedidos_com_bicicleta", "Só pedidos com bicicleta", PURPLE)]):
    barras = ax.bar(xp + deslocamento, promocao[coluna], 0.4, color=cor, label=nome)
    ax.bar_label(barras, labels=[br(v) for v in promocao[coluna]], fontsize=9, padding=2)
ax.set_xticks(xp, [f"{g}\n({pct(promocao.loc[g, 'pct_com_bicicleta'], 0)} dos pedidos têm bicicleta)" for g in promocao.index])
ax.set_ylim(0, promocao[["ticket_medio", "ticket_pedidos_com_bicicleta"]].max().max() * 1.22)
ax.yaxis.set_major_formatter(inteiro)
ax.set_ylabel("US$ por pedido")
ax.set_title("Ticket médio online com e sem o motivo Promotion", loc="left")
ax.legend(loc="upper center", ncol=2)
plt.show()

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **À primeira vista, a promoção quase dobra o ticket:** pedidos que citam "On Promotion" têm ticket médio de US$ 1.810, contra US$ 952 nos demais.
# MAGIC - **Mas a comparação é injusta:** 100% dos pedidos com o motivo Promotion têm bicicleta, contra 48,4% dos demais. Comparando só pedidos com bicicleta, o ticket é US$ 1.810 com o motivo e US$ 1.913 sem ele. O efeito desaparece (e até inverte): a diferença inicial é de mix de produto, não de comportamento.
# MAGIC - **Não há desconto em nenhum dos dois grupos.** "On Promotion" é o motivo declarado pelo cliente, sem uma oferta especial ou desconto registrado no pedido. Com os dados atuais, não é possível medir retorno de promoção.
# MAGIC - **Ação:** registrar as promoções do online como ofertas especiais (com desconto, período e produtos) para medir o efeito real em volume e margem.

# COMMAND ----------

# Business question: which product sells the most under the "On Promotion" reason?
mais_vendidos_promocao = q(f"""
SELECT p.nome_produto AS produto, p.nome_categoria AS categoria, CAST(SUM(f.quantidade) AS BIGINT) AS quantidade,
  CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_produtos p ON p.pk_produto = f.fk_produto
WHERE array_contains(split(f.motivos_venda, ', '), 'On Promotion')
GROUP BY ALL ORDER BY quantidade DESC, produto LIMIT 10
""")
fig, ax = plt.subplots(figsize=(11, 4.2))
ordem = mais_vendidos_promocao.iloc[::-1]
barras = ax.barh(ordem["produto"], ordem["quantidade"], color=[ORANGE if c != "Bikes" else TEAL for c in ordem["categoria"]])
ax.bar_label(barras, labels=[br(v) for v in ordem["quantidade"]], fontsize=8, padding=3)
ax.set_xlabel("unidades")
ax.set_title('Top 10 produtos por quantidade com o motivo "Promotion" (laranja: acessórios e roupas)', loc="left")
plt.show()
display(mais_vendidos_promocao)

lider_valor = q(f"""
SELECT p.nome_produto AS produto, CAST(SUM(f.valor_bruto_linha) AS DOUBLE) AS valor_bruto,
  CAST(SUM(f.quantidade) AS BIGINT) AS quantidade
FROM {MARTS}.fct_pedidos_vendas f
JOIN {MARTS}.dim_produtos p ON p.pk_produto = f.fk_produto
WHERE array_contains(split(f.motivos_venda, ', '), 'On Promotion')
GROUP BY ALL ORDER BY valor_bruto DESC, produto LIMIT 1
""").iloc[0]
lider_qtd = mais_vendidos_promocao.iloc[0]
print(f"Mais vendido com o motivo Promotion, por quantidade: {lider_qtd['produto']} ({br(lider_qtd['quantidade'])} unidades)")
print(f"Mais vendido com o motivo Promotion, por valor: {lider_valor['produto']} "
      f"(US$ {br(lider_valor['valor_bruto'])}, {br(lider_valor['quantidade'])} unidades)")

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights (pergunta de negócio: produto mais vendido sob o motivo "Promotion")**
# MAGIC - **Por quantidade, o mais vendido é a Water Bottle - 30 oz.** (546 unidades), seguida do Road Bottle Cage (416) e do boné AWC Logo Cap (301): acessórios baratos que acompanham a bicicleta no mesmo pedido.
# MAGIC - **Por valor, o líder é a bicicleta Mountain-200 Black, 42** (299 unidades), a primeira bicicleta do ranking por quantidade. É ela que concentra o dinheiro dentro da promoção.
# MAGIC - O dashboard responde à pergunta por quantidade (unidades vendidas), que é o sentido literal de "mais vendido". A leitura por valor fica registrada aqui como complemento.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Formas de pagamento

# COMMAND ----------

cartoes = q(f"""
SELECT f.tipo_cartao, {CANAL_SQL} AS canal, COUNT(DISTINCT f.fk_pedido_venda) AS pedidos,
  CAST(SUM(f.valor_total_linha) / COUNT(DISTINCT f.fk_pedido_venda) AS DOUBLE) AS ticket_medio
FROM {MARTS}.fct_pedidos_vendas f GROUP BY ALL
""")
cartoes["pct_pedidos_canal"] = cartoes["pedidos"] / cartoes.groupby("canal")["pedidos"].transform("sum")
tabela_cartoes = cartoes.pivot_table(index="tipo_cartao", columns="canal", values="pct_pedidos_canal", fill_value=0)
fig, ax = plt.subplots(figsize=(11, 4))
xc = np.arange(len(tabela_cartoes))
for deslocamento, canal in zip([-0.2, 0.2], ["Online", "Revenda (lojas)"]):
    barras = ax.bar(xc + deslocamento, tabela_cartoes[canal] * 100, 0.4, color=CANAL_CORES[canal], label=canal)
    ax.bar_label(barras, labels=[pct(v, 0) for v in tabela_cartoes[canal]], fontsize=8, padding=2)
ax.set_xticks(xc, tabela_cartoes.index)
ax.set_ylabel("% dos pedidos do canal")
ax.set_title("Pedidos por tipo de cartão (N/A = pedido sem cartão)", loc="left")
ax.legend()
plt.show()
display(cartoes.sort_values(["canal", "pedidos"], ascending=[True, False]).round(4))

# COMMAND ----------

# MAGIC %md
# MAGIC **Insights**
# MAGIC - **As quatro bandeiras dividem os pedidos quase em partes iguais.** No online, cada uma tem entre 23% e 25% dos pedidos e o ticket médio quase não muda entre elas (cerca de US$ 1.040 a 1.100). Na revenda a divisão vai de 20% (Distinguish) a 28% (ColonialVoice).
# MAGIC - Pedidos sem cartão (N/A) são 4,1% do online e 0,2% da revenda.
# MAGIC - O tipo de cartão quase não diferencia o comportamento de compra. Ele está no dashboard porque o desafio pede, mas não é onde estão as decisões.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 12. Conclusões e implicações para o dashboard
# MAGIC
# MAGIC ### O que a análise mostrou
# MAGIC 1. **Dois negócios em uma base.** A revenda (635 lojas) gera 73% do valor com 12% dos pedidos. O online (18,5 mil clientes) gera 88% dos pedidos e 27% do valor. Quase toda métrica muda de sentido quando os canais são misturados.
# MAGIC 2. **O ticket médio caiu por mix, não por perda.** Bicicletas mais baratas (2012 e 2013) e a entrada de acessórios e roupas no online (2013) multiplicaram os pedidos e reduziram o ticket. Dentro da revenda, o ticket caiu só 20%.
# MAGIC 3. **2014 está crescendo.** De janeiro a maio, o valor subiu 46,7% sobre o mesmo período de 2013. O ano parece menor apenas por ter 6 meses, e junho/2014 é atípico.
# MAGIC 4. **A receita é concentrada.** 24% dos produtos e 8% dos clientes fazem 80% do valor. Metade dos produtos vendidos (classe C) gera 5%.
# MAGIC 5. **"Promotion" não é uma promoção mensurável.** O motivo aparece só em pedidos com bicicleta, não tem desconto associado e, comparando pedidos equivalentes, não eleva o ticket.
# MAGIC
# MAGIC ### Decisões de modelagem e de dashboard que vieram da EDA
# MAGIC | Achado | Decisão |
# MAGIC |---|---|
# MAGIC | 73,4% do valor vem de clientes sem endereço próprio | Localização pelo **endereço de entrega do pedido** (`dim_localidades` ligada à fato por `fk_localidade`) |
# MAGIC | Chaves de pedido e item íntegras; pedido × produto único | Fato no grão de **item do pedido**; pedido como dimensão degenerada; número de pedidos = contagem distinta |
# MAGIC | Preço arredondado erra a auditoria em US$ 6,58 | Preço em `decimal(18,4)` no staging e teste de auditoria com o valor **exato** de 2011 |
# MAGIC | 1.131 pedidos sem cartão; revenda e 4.647 pedidos online sem motivo | Valores explícitos **N/A** e **Nenhum**, para não esconder linhas nos filtros |
# MAGIC | Ticket e localização dependem do canal | Campo **Canal de venda** em todas as páginas e análise de canais lado a lado |
# MAGIC | Revenda concentrada na virada do mês | Séries temporais **mensais**, não diárias |
# MAGIC | 266 produtos, 19.119 clientes, cidades homônimas | Rankings **Top N** (Top 20, 10 e 5) e cidade agrupada com estado e país |
# MAGIC | Concentração de produtos e clientes | Página de **Pareto / curva ABC** com a mesma regra (A até 80%, B até 95%) |
# MAGIC | Rankings precisam responder a qualquer recorte | Rankings recalculados com **todos os filtros** (parâmetros aplicados antes do Top N) |
# MAGIC
# MAGIC ### Recomendações para o negócio
# MAGIC 1. **Comparar sempre períodos equivalentes** (mesmos meses de cada ano) e tratar junho/2014 como mês incompleto.
# MAGIC 2. **Gestão de contas-chave na revenda:** 494 das 635 lojas estão na classe A. Acompanhar frequência e valor de cada loja e agir quando uma loja pula o ciclo mensal.
# MAGIC 3. **Recompra no online:** 63% dos clientes compraram uma única vez. Campanhas pós-compra (acessórios e roupas para quem comprou bicicleta) atacam o maior potencial de crescimento do canal.
# MAGIC 4. **Registrar promoções como ofertas especiais** (desconto, período, produtos) para medir o retorno, em vez de depender do motivo declarado pelo cliente.
# MAGIC 5. **Revisar o sortimento da classe C** (137 produtos com 5,1% do valor) e garantir disponibilidade da classe A.
# MAGIC 6. **Ler ticket médio junto com o mix** (canal e categoria). Um ticket em queda com volume em alta pode ser estratégia, não problema.
# MAGIC 7. **Qualidade de dados:** capturar o motivo de venda também na revenda, registrar o cartão nos 1.131 pedidos sem ele e revisar o status, hoje com um único valor ("Enviado"), que não permite acompanhar o ciclo do pedido.
