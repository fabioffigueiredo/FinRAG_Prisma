# Parecer — Sinais preditivos no Prisma (probabilidade de ganho/perda por fundo)

**Pergunta:** com a base temporal de fundos da gestora (séries, índices, causas de
ganho/perda) + sentimento de notícias, o Prisma pode informar ao gestor
probabilidades de rendimento/perda e sugerir proatividade? Isso é válido?

## Veredicto: SIM, é válido e é um diferencial — com três condições de desenho

É a evolução natural do produto ("Prisma Sinais", fase 2) e o que o gestor mais
valoriza. Mas só sustenta escrutínio (do gestor, do risco e do regulador) se:

1. **Quem prevê é um modelo quantitativo, nunca a LLM.** O sinal sai de um modelo
   estatístico backtestado (ex.: prob. condicional de retorno negativo da
   estratégia X dado sentimento em deterioração + cenário de juros), com métrica
   publicada (acurácia out-of-sample, janelas). A LLM continua no papel que já
   domina: **explicar o sinal citando as evidências** — mantém a tese "explica,
   não inventa".
2. **Enquadramento de alerta, não de ordem.** A saída é "em 68% das 25 janelas
   semelhantes desde 2019, esta estratégia teve retorno negativo no mês seguinte"
   — nunca "venda/reduza". O gestor decide; o sistema informa e registra. O
   guardrail atual de escopo evolui: continua recusando recomendação direta, mas
   passa a apresentar **cenários probabilísticos com histórico e confiança**.
3. **Governança de modelo desde o dia 1.** Versão do modelo, dados de treino,
   backtest reproduzível e trilha de auditoria de cada sinal exibido — o mesmo
   padrão que já usamos para as respostas do copiloto.

## Base regulatória (por que é permitido)

- A [Resolução CVM 20](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol020consolid.pdf)
  regula **relatórios de análise e recomendações dirigidos a investidores**. Uma
  ferramenta **interna** de apoio à decisão do gestor profissional — sobre os
  próprios fundos da casa — não é relatório de análise ao público; é prática
  padrão de mesa quantitativa. (Se algum conteúdo do sinal for distribuído a
  cotistas, aí sim entra no regime da CVM 20/30 — manter interno.)
- A CVM já reconhece **sistemas automatizados/algoritmos** na atividade de
  consultoria/análise, exigindo responsabilidade e código auditável — exatamente a
  postura de auditoria que o Prisma já tem ([interpretações CVM](https://www.compliasset.com/alerta/cvm-divulga-interpretacoes-sobre-consultoria-de-valores-mobiliarios/)).
- O que NÃO pode: virar recomendação individualizada a cliente sem os regimes de
  suitability ([CVM 30](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol030consolid.pdf)).

## Base acadêmica (o sinal existe, e é modesto — dizer isso é força, não fraqueza)

- [Tetlock (2007)](https://www.researchgate.net/publication/4992763_Giving_Content_to_Investor_Sentiment_The_Role_of_Media_in_the_Stock_Market):
  pessimismo na mídia prevê retornos e volume de curto prazo — o clássico da área.
- Horizonte: o poder preditivo do sentimento está documentado no **curto prazo
  (dias a ~6 meses)** e enfraquece depois ([análise multi-horizonte](https://www.sciencedirect.com/science/article/abs/pii/S027553192400494X),
  [índices globais de sentimento](https://www.tandfonline.com/doi/full/10.1080/23322039.2026.2613996)).
- Fundos: hedge funds com baixa exposição ao sentimento macro superam os de alta
  exposição em ~0,41%/mês ([macro sentiment & hedge funds](https://www.sciencedirect.com/science/article/abs/pii/S0378426626000592));
  fundos que processam texto de filings geram excesso de retorno.
- Implicação honesta para o pitch: sentimento é **um fator com sinal real e
  modesto**, útil para **antecipação de risco e priorização de atenção** — não uma
  bola de cristal. Vender assim gera credibilidade com quem é de mesa.

## Como fica no produto (Prisma Sinais — fase 2)

```
Base temporal da gestora (séries de fundos, benchmarks, causas)   ─┐
Sentimento de notícias por estratégia (radar, já existe)          ─┼─▶ Modelo quant
Cenário de mercado (juros, índices)                               ─┘   (backtest)
                                                                        │ prob. + confiança + histórico
                                                                        ▼
                                          LLM explica o sinal com citações (já existe)
                                                                        ▼
                                     Tela "Sinais": alerta por fundo/estratégia + trilha
```

**MVP do piloto (com os dados da gestora):**
1. *Early warning* por estratégia: prob. condicional de contribuição negativa no
   próximo período, dado sentimento + regime de mercado (modelo simples e
   auditável: regressão logística/gradient boosting raso, janelas móveis).
2. Backtest publicado na própria tela (hit rate, precisão/cobertura por regime).
3. Narrativa da LLM: "o sinal está elevado porque X notícias negativas de varejo +
   histórico de 2019-2024 em regime de juros altos — evidências: […]".
4. Ação sugerida sempre no formato "atenção/priorize revisar", nunca ordem.

**Frase para o gestor:** "hoje o Prisma explica o retorno que aconteceu; com a
base de vocês, ele passa a apontar onde olhar antes do próximo fechamento — com a
probabilidade medida e auditada, e a decisão continua com o gestor."
