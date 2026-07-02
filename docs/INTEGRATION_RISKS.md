# Prisma — Riscos de Integração e Mitigações

| # | Risco | Impacto | Mitigação |
|---|---|---|---|
| 1 | Aprovação de modelo de IA no banco | bloqueia produção | Backend pluggável (`get_llm`): troca por modelo homologado internamente sem tocar o produto; POC já roda 100% local (Ollama) |
| 2 | Alucinação em conteúdo financeiro | credibilidade/compliance | Geração só sobre números já calculados + citações obrigatórias + guardrail de escopo (não recomenda/não prevê) + temperatura baixa |
| 3 | Prompt injection via documentos | manipulação de respostas | Guardrail de sanitização já demonstrado; trechos bloqueados ficam visíveis e auditados |
| 4 | Ambiente corporativo sem registries públicos (npm/pip) | build em prod | Bundle Next.js pré-compilado + mirror interno de pacotes para Python |
| 5 | Licença do provedor de dados de mercado | jurídico | Dados VaR nunca expostos por API pública; permanecem no perímetro corporativo |
| 6 | Encoding legado (latin-1/UTF-8) | dados corrompidos | Normalização na ingestão (lição documentada da plataforma de atribuição do cliente) |
| 7 | Sentimento PT com modelo treinado em EN | qualidade do radar | Rotulagem dupla no POC (SVM FinNLP + LLM local) com decisão documentada; fase 2 avalia modelo PT dedicado |
| 8 | Dados sensíveis em log | LGPD | Auditoria grava hash da resposta (não o texto), sem PII; corpus do POC é 100% fictício |
| 9 | Latência do LLM local em demo | experiência | Warmup no startup + narrativa sob demanda (botão) + motor alternável para Groq |
| 10 | Dependência de uma pessoa (autor) | continuidade | Specs/planos versionados no repo; arquitetura modular documentada |
