# Metodologia de Atribuição de Performance

A atribuição de performance decompõe o retorno de um fundo em um período no
**quanto cada ativo, estratégia e grupo contribuiu** para o resultado da cota.
Não é uma atribuição de Brinson (alocação vs seleção) nem baseada em fatores: é
uma **atribuição por contribuição**, construída a partir dos dados contábeis e de
carteira do fundo.

## Contribuição diária de um ativo

A contribuição diária de cada ativo é calculada como a variação do seu resultado
no dia dividida pelo patrimônio líquido do dia anterior (D-1):

    contribuição_dia = ( SALDO_dia − SALDO_D-1 + PROVENTOS_dia ) / PATRIMONIO_D-1

Onde `PROVENTOS` são rendimentos, juros ou cupons pagos no dia. Somar a parcela de
proventos evita subestimar a contribuição de ativos que pagam cupom (títulos
públicos indexados, debêntures).

## Composição no período (ajuste)

As contribuições diárias são **compostas** ao longo do período (o "ajuste"), de
forma que a **soma das contribuições ajustadas de todos os ativos seja igual ao
retorno da cota** no período. Sem o ajuste de composição, a soma simples das
contribuições diárias não fecharia com o retorno da cota por causa do efeito de
juros sobre juros.

## Regra de validação

O sistema valida que `soma(contribuições por estratégia) ≈ retorno da cota` (com
tolerância pequena). Quando não fecha, há um ativo com sinal invertido, um
provento não capturado ou uma inconsistência de dados a investigar.

## Correções de sinal

Alguns grupos contábeis registram valores com sinal invertido em relação ao efeito
econômico (por exemplo, certas posições passivas ou de despesa). Nesses grupos o
sinal da contribuição é corrigido antes da composição, para que uma posição que
**adicionou** retorno apareça como contribuição positiva.

## Fundos que investem em fundos (FIC/FI)

Em estruturas fundo-de-fundos (FIC investindo em um ou mais FI "master"), o
resultado do FIC é comparado ao resultado atribuído dos masters. O
**Diferencial FIC** é a diferença entre o retorno observado do FIC e a soma das
contribuições vindas dos fundos investidos; um diferencial próximo de zero indica
que a atribuição está capturando corretamente o resultado consolidado.
