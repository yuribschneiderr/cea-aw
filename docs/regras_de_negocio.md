# Regras de Negócio — Adventure Works

Documento de regras de negócio do pipeline de vendas (Databricks + dbt) e do dashboard **Adventure Works - Painel de Vendas**. Ele define o que cada indicador mede, de onde vem cada dado e como os filtros se comportam, para que qualquer número do dashboard possa ser explicado e reproduzido.

## 1. Escopo

| Item | Regra |
|---|---|
| Fonte | Somente o schema `adventure_works` do workspace Databricks (cópia das tabelas transacionais da Adventure Works). |
| Assunto | Vendas: pedidos de venda e seus itens. Compras, produção e RH estão fora do escopo. |
| Período disponível | 31/05/2011 a 30/06/2014. **2011 e 2014 são anos incompletos**: maio/2011 tem só o dia 31 e junho/2014 é atípico (só pedidos online, sem bicicletas e sem revenda). |
| Moeda | US$, como registrado na base. Não há conversão de moeda. |
| Camada consumida | `marts`: a fato `fct_pedidos_vendas` e as dimensões `dim_clientes`, `dim_produtos`, `dim_localidades`, `dim_datas`, `dim_metodos_envio` e `dim_ofertas_especiais`. |

## 2. Perguntas de negócio e onde são respondidas

| # | Pergunta | Indicadores | Onde no dashboard |
|---|---|---|---|
| 1 | Quantos pedidos, quantas unidades e qual o valor total negociado, por produto, tipo de cartão, motivo de venda, cliente, status, cidade, estado e país? | Número de pedidos, Quantidade comprada, Valor total negociado | Página **Visão geral** (indicadores) e página **Análise por dimensão** (um visual por dimensão). Qualquer combinação pelos filtros globais. |
| 2 | Qual o ticket médio mensal e anual por localização? | Ticket médio | *Ticket médio mensal* (Visão geral) e *Ticket médio anual por país* (Análise por dimensão), recortados pelos filtros de cidade, estado e país. |
| 3 | Quais produtos têm o maior ticket médio por mês, ano, cidade, estado e país? | Ticket médio do produto | *Top 20 produtos por ticket médio* (Análise por dimensão), com os filtros de período e de localização. |
| 4 | Quem são os 10 maiores clientes por valor total negociado, por produto, tipo de cartão, motivo de venda, data, status e localização? | Valor total negociado | *Top 10 clientes por valor total negociado*: o ranking é recalculado para os filtros selecionados. |
| 5 | Quais são as 5 maiores cidades por valor total negociado, pelos mesmos filtros e por cliente? | Valor total negociado | *Top 5 cidades por valor total negociado*: o ranking é recalculado para os filtros selecionados. |
| 6 | Como pedidos e faturamento evoluem no tempo? | Número de pedidos, Valor total negociado, Quantidade comprada, Ticket médio | Série mensal na **Visão geral**: faturamento em destaque e, abaixo, pedidos, quantidade e ticket médio. |
| 7 | Qual o produto mais vendido nos pedidos com o motivo "Promotion"? | Quantidade comprada | *Top 10 produtos mais vendidos com o motivo "Promotion"* (Análise por dimensão). |
| 8 | Quão concentradas são as vendas? A promoção funciona? Qual canal sustenta o negócio? | % acumulado, Classe ABC, Ticket médio por grupo, Valor por canal | Página **Análises avançadas** (perguntas complementares levantadas na análise exploratória). |

## 3. Indicadores (KPIs)

### 3.1 Definições

| Indicador | Definição | Cálculo | Por que é usado |
|---|---|---|---|
| **Número de pedidos** | Pedidos distintos no recorte. | Contagem distinta do número do pedido. | Mede volume de transações, independentemente do tamanho de cada pedido. |
| **Quantidade comprada** | Unidades vendidas. | Soma da quantidade dos itens. | Mede volume físico (estoque, logística). Separa "vender mais unidades" de "vender mais caro". |
| **Valor total negociado** | Valor dos itens antes do desconto. É o **faturamento** usado no dashboard. | Soma de preço unitário × quantidade. | É o valor pedido no desafio e o valor da auditoria contábil de 2011. Ordena todos os rankings e o Pareto. |
| **Desconto concedido** | Valor abatido pelas ofertas especiais. | Soma de preço unitário × quantidade × desconto unitário. | Mostra quanto do valor negociado não foi cobrado e em quais ofertas. |
| **Valor líquido** | Valor efetivamente cobrado pelos itens. | Valor total negociado − desconto concedido. | Base do ticket médio. Bate com o subtotal do cabeçalho dos pedidos. |
| **Ticket médio** | Valor líquido médio por pedido. | Valor líquido ÷ número de pedidos. | Mede o tamanho do pedido. Usa o líquido porque é o que o cliente pagou pelos produtos (sem frete e imposto). |
| **Ticket médio do produto** | Valor líquido médio do produto em cada pedido em que ele aparece. | Valor líquido do produto ÷ pedidos com o produto. | Responde à pergunta 3 sem misturar o valor dos outros produtos do pedido. |
| **Participação (%)** | Peso de uma parte no total do recorte selecionado. | Valor da parte ÷ valor total do recorte × 100. | Compara partes de tamanhos diferentes e é a barra do Pareto. |
| **% acumulado** | Quanto do valor os itens maiores somam até aquele ponto. | Soma acumulada do valor total negociado, do maior para o menor, ÷ total. | É a linha do Pareto. |
| **Classe ABC** | Grupo de importância de produtos e clientes. | **A** = até 80% do valor acumulado, **B** = de 80% a 95%, **C** = restante. | Prioriza sortimento, estoque e atendimento. |
| **Itens por pedido** | Unidades médias por pedido. | Quantidade comprada ÷ número de pedidos. | Separa o efeito do tamanho da cesta do efeito do preço na comparação da promoção. |
| **Primeira compra / Recompra** | Tipo de cada pedido para o cliente. | Primeira compra = pedido feito na data do primeiro pedido do cliente (histórico completo). Os demais são recompra. | Mostra quanto do faturamento vem de clientes que voltam. |

### 3.2 Valores de referência (base completa, sem filtros)

| Indicador | Valor |
|---|---|
| Número de pedidos | 31.465 |
| Quantidade comprada | 274.914 unidades |
| Valor total negociado | US$ 110.373.889,31 |
| Desconto concedido | US$ 527.507,91 (0,48% do valor negociado) |
| Valor líquido | US$ 109.846.381,40 |
| Ticket médio | US$ 3.491,07 |
| Clientes com pedido | 19.119 (de 19.820 cadastrados) |
| Produtos vendidos | 266 (de 504 cadastrados) |
| Valor total negociado em 2011 (auditado) | **US$ 12.646.112,16** |

Por canal:

| Canal | Pedidos | Valor total negociado | % do valor | Ticket médio | Clientes |
|---|---|---|---|---|---|
| Revenda (lojas) | 3.806 | US$ 81.015.212,09 | 73,4% | US$ 21.147,58 | 635 |
| Online | 27.659 | US$ 29.358.677,22 | 26,6% | US$ 1.061,45 | 18.484 |

Esses valores servem de conferência: com todos os filtros vazios, o dashboard deve mostrar exatamente estes números.

## 4. Regras dos dados

### 4.1 Granularidade e chaves

- A fato `fct_pedidos_vendas` tem **uma linha por item do pedido** (121.317 linhas). Cada produto aparece no máximo uma vez por pedido.
- O número do pedido fica na própria fato (dimensão degenerada). O número de pedidos é sempre uma **contagem distinta**, nunca uma contagem de linhas.
- Os valores do cabeçalho do pedido (subtotal, imposto, frete, total devido) se repetem em cada item e **não são somados** no grão de item. Todos os indicadores de venda partem dos itens.

### 4.2 Valores monetários

- Preço unitário e desconto unitário são mantidos com **4 casas decimais**, como na origem. Os valores de cada item são calculados com precisão total e arredondados apenas na exibição.
- Arredondar o preço para 2 casas antes de multiplicar muda o valor de 2011 em US$ 6,58 e reprova a auditoria.
- Desconto real só existe nas **ofertas especiais**, e elas só aparecem em vendas para revenda (lojas). Todo item tem uma oferta; sem desconto, a oferta é "No Discount".

### 4.3 Data

- A data de referência de todos os indicadores é a **data do pedido**. Datas de vencimento e de envio não entram nos indicadores.
- As séries temporais são **mensais**. A revenda concentra os pedidos na virada do mês, e uma série diária ficaria serrilhada sem trazer informação.

### 4.4 Status do pedido

- Código convertido em descrição: 1 Em processamento, 2 Aprovado, 3 Em espera, 4 Rejeitado, 5 Enviado, 6 Cancelado.
- Nenhum pedido é excluído por status. Na base atual **todos os pedidos estão "Enviado"**, por isso o gráfico de status tem uma única fatia.

### 4.5 Localização

- Cidade, estado e país vêm do **endereço de entrega do pedido**, e não do cadastro do cliente.
- Motivo: clientes do tipo loja não têm endereço pessoal. Pelo cadastro, 73,4% do valor ficaria sem cidade. Todo pedido tem endereço de entrega.
- Uma cidade é identificada por **cidade + estado + país**, porque há nomes de cidade repetidos em estados diferentes. O ranking Top 5 cidades agrupa por essas três colunas.

### 4.6 Cliente

- O cliente é identificado pelo código do cadastro. O nome exibido é o da pessoa vinculada ao cliente; nas lojas, é o contato da loja.
- No dashboard o cliente aparece como **"Nome (código)"**, porque nomes podem se repetir. Cliente sem pessoa vinculada aparece como "Sem nome".

### 4.7 Canal de venda

- **Online**: pedido feito pelo site, por clientes pessoa física.
- **Revenda (lojas)**: pedido feito por representante de vendas, para lojas.
- Na base, o canal e o tipo de cliente coincidem um a um. Ticket, mix de produtos e localização mudam muito de um canal para o outro, por isso o canal está disponível como filtro em todas as páginas.

### 4.8 Tipo de cartão

- O tipo do cartão de crédito usado no pedido.
- Pedido sem cartão recebe **"N/A"** (1.131 pedidos), para não sumir dos filtros e dos gráficos.

### 4.9 Motivo de venda

- Motivo declarado no pedido. Um pedido pode ter vários; a fato guarda a **lista ordenada** dos motivos, separada por vírgula (por exemplo, "On Promotion, Price").
- Pedido sem motivo recebe **"Nenhum"**. Isso vale para todos os pedidos da revenda e para 4.647 pedidos online.
- O filtro "Motivo de venda" lista essas combinações. No gráfico *Valor total negociado por motivo de venda*, um pedido com dois motivos conta nos dois, então a soma das barras passa do total.
- O motivo "Promotion" do desafio aparece na base como **"On Promotion"**. Ele só existe no canal online e **não tem desconto associado**: é o motivo declarado pelo cliente, não uma campanha com preço reduzido.

### 4.10 Produto

- Hierarquia: produto → subcategoria → categoria (Bikes, Components, Clothing, Accessories), com os nomes como estão na origem.

## 5. Regras do dashboard

### 5.1 Filtros globais

- Ficam na página de filtros globais e **valem para as três páginas**: Período do pedido, País, Estado, Cidade, Produto, Cliente, Tipo de cartão, Motivo de venda, Status do pedido e Canal de venda.
- Filtro sem seleção = todos os valores. O período padrão é o histórico completo (31/05/2011 a 30/06/2014).
- O filtro de **Produto** não se aplica aos visuais calculados por pedido inteiro: o indicador *Ticket médio*, *Ticket médio mensal*, *Ticket médio anual por país*, *Ticket médio mensal por canal* e as comparações do motivo "Promotion". Um pedido pode ter vários produtos, e filtrar um deles distorceria o valor do pedido. Para o ticket de um produto, use o ranking *Top 20 produtos por ticket médio*.

### 5.2 Rankings (Top N)

| Ranking | Ordenado por | Limite | Motivo do limite |
|---|---|---|---|
| Top 20 produtos | Valor total negociado | 20 | 266 produtos vendidos não cabem em um gráfico de barras legível. |
| Top 20 produtos por ticket médio | Ticket médio do produto | 20 | Idem. |
| Top 20 estados | Valor total negociado | 20 | 70 estados. |
| Top 10 clientes | Valor total negociado | 10 | Pedido do desafio. |
| Top 5 cidades | Valor total negociado | 5 | Pedido do desafio. |
| Top 10 produtos com o motivo "Promotion" | Quantidade comprada | 10 | Responde "mais vendido" em unidades. |

- Os rankings são **recalculados para a seleção**: os filtros são aplicados antes de agrupar e cortar o Top N. Exemplo: o Top 10 clientes da França em 2013 é o ranking dos clientes da França em 2013, e não o Top 10 geral recortado para a França.
- Nos rankings por valor e por ticket médio, o empate é desfeito pelo nome, para que o ranking seja sempre o mesmo.

### 5.3 Pareto e curva ABC

- Produtos e clientes são ordenados do maior para o menor valor total negociado e divididos em **10 faixas de mesmo tamanho** (10% dos itens cada).
- Barra = % do valor na faixa. Linha = % acumulado até a faixa. Os dois estão na mesma escala (0 a 100%), com uma linha de referência em 80%.
- A classe ABC usa a regra da seção 3.1. Como os filtros são aplicados antes do cálculo, a classe de um produto pode mudar conforme o recorte.

### 5.4 Leitura correta dos números

- **Comparar períodos equivalentes.** 2014 tem só 6 meses: comparar o ano cheio de 2013 com 2014 subestima 2014. De janeiro a maio, o valor total negociado de 2014 foi 46,7% maior que o de 2013.
- **Ler o ticket médio junto com o mix.** A entrada de bicicletas mais baratas e de acessórios e roupas no online multiplicou os pedidos e reduziu o ticket médio geral. Uma queda do ticket com volume em alta pode ser estratégia, e não perda.
- **Separar os canais.** A revenda tem 12% dos pedidos e 73% do valor; o online tem o inverso. Misturar os dois esconde o comportamento de cada um.

## 6. Qualidade de dados e testes

O dbt executa 64 testes a cada carga. Se um falha, a execução é reprovada.

| Tipo | O que garante |
|---|---|
| Chave única e não nula nas tabelas de origem | Cada registro da origem é identificável, inclusive nas tabelas de chave composta. |
| Chave única e não nula nos modelos intermediários, em todas as dimensões e na fato | Nenhuma linha duplicada ou sem chave chega ao dashboard. |
| Integridade referencial | As 6 chaves estrangeiras da fato (data, cliente, localidade, método de envio, produto e oferta especial) existem nas dimensões. |
| **Auditoria contábil** | O valor total negociado de 2011 (preço unitário × quantidade, arredondado a 2 casas) é **exatamente US$ 12.646.112,16**, sem tolerância. |

Conferência feita na análise exploratória: a soma dos itens bate com o subtotal do cabeçalho em todos os 31.465 pedidos (0 pedidos divergentes).

## 7. Limitações conhecidas

- **Status único:** todos os pedidos estão "Enviado". Não é possível analisar cancelamentos, rejeições ou tempo de ciclo.
- **Motivo de venda só no online:** a revenda não registra motivo, então análises por motivo valem apenas para o canal online.
- **"On Promotion" não mede promoção:** sem desconto e sem período associados, não é possível medir o retorno de uma campanha por esse campo.
- **Bordas do período:** maio/2011 e junho/2014 não devem ser usados para tendência.
- **Cadastros sem venda:** 701 clientes e 238 produtos cadastrados não têm venda e não aparecem nos indicadores.
- **Cartão ausente:** 1.131 pedidos sem cartão aparecem como "N/A".
