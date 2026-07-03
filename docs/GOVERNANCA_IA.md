# Governança de IA do Prisma

Este documento descreve os controles que tornam o Prisma adequado a um ambiente
financeiro regulado. Aplica-se ao POC e é o alicerce contratual para o piloto.

## 1. Princípio de escopo: explicar, não recomendar

O Prisma **explica** resultados de atribuição já calculados e **sinaliza** riscos
com probabilidade — nunca emite recomendação de compra/venda nem promete
resultado. Pedidos de recomendação são recusados por regra determinística
(guardrail de escopo), antes de qualquer modelo de linguagem.

- Base: a [Resolução CVM 20](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol020consolid.pdf)
  regula relatórios de análise e recomendações dirigidos a investidores. O Prisma
  é ferramenta **interna** de apoio à decisão do gestor sobre os próprios fundos —
  não distribui recomendação a investidor. Conteúdo destinado a cotistas exigiria
  o regime de suitability ([CVM 30](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol030consolid.pdf)) e fica fora do escopo.

## 2. Separação de responsabilidades (quem faz o quê)

| Componente | Papel | O que NÃO faz |
|---|---|---|
| Modelo de regras (`sinais.py`) | Estima probabilidade de risco (transparente, auditável) | Não decide, não recomenda |
| RAG + LLM | **Explica** números e sinais, citando fontes | Não calcula números, não prevê sozinho |
| Guardrail de escopo (`escopo.py`) | Barra recomendação/previsão fora de escopo | — |
| Guardrail de injeção (`guardrails.py`) | Bloqueia comando malicioso em documento | — |
| Gestor (humano) | Decide e aprova o comentário | — |

## 3. Sinais probabilísticos — formato e avisos

Todo sinal é apresentado como **alerta de atenção**, nunca como ordem, sempre com:

- **Nível**: `ok` · `atenção` (prob. ≥ 45%) · `alerta` (prob. ≥ 60%);
- **Probabilidade** de contribuição negativa no próximo período;
- **Base de cálculo** explícita (a fórmula, versão do modelo);
- **Evidências** (notícias citadas por id) + sentimento e contribuição corrente;
- **Aviso legal** fixo (abaixo);
- **Estado de validação**: v0 sem backtest; v1 (piloto) com hit-rate publicado.

> **Aviso legal exibido junto de todo sinal:**
> Sinal probabilístico de APOIO À DECISÃO, gerado por modelo de regras auditável
> sobre dados do período. NÃO constitui recomendação de compra ou venda, análise
> de valores mobiliários (Res. CVM 20) ou garantia de resultado. Uso interno; a
> decisão é sempre do gestor.

## 4. Aprovação humana obrigatória (human-in-the-loop)

Nenhum comentário gerado vai a comitê/cliente sem revisão. O fluxo tem estado
explícito: **rascunho → em revisão → aprovado** (com autor e horário do aprovador),
e só o aprovado pode ser exportado. Isso está demonstrado na tela de Relatório.

## 5. Rastreabilidade e auditoria

- Cada consulta (narrativa, Q&A, sinal) registra: horário, fundo, pergunta, motor,
  fontes citadas, trechos bloqueados e hash da resposta — sem dados pessoais.
- Modelos são versionados (`modelo_versao`); no piloto, o backtest é reproduzível.
- Aprovações de comentário ficam registradas (quem/quando).

## 6. Privacidade e soberania do dado

- IA executável **100% local** (Ollama) — nenhum dado sai da máquina;
- Alternativa em nuvem via chave de API, para casos sem dado sensível;
- Backend de LLM pluggável: em produção, usa-se o modelo homologado internamente.

## 7. Dados do POC

Todos os fundos, notícias e números do POC são **fictícios**. Nenhuma instituição
real é citada. A validação estatística dos sinais ocorre apenas no piloto, com a
base real e sob a governança acima.
