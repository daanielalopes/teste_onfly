# Declaração de uso de IA

## Ferramenta e modelo

- **Ferramenta:** Kiro (ambiente de desenvolvimento com IA integrado ao editor).
- **Modelo:** Auto (seleção dinâmica de modelo no servidor).

## O que a IA fez

- Analisou a arquitetura do projeto (CLI, modelos, repositórios e serviços) e o contrato descrito no
  `README.md`.
- Executou o `pytest` e associou cada falha ao ponto de código responsável.
- Propôs e aplicou as correções pontuais nos cinco defeitos, mantendo schema, semântica dos campos,
  testes fornecidos e dados de entrada inalterados.
- Reexecutou os testes e validou o resultado contra a amostra `data/exemplo-validacao.csv`.
- Redigiu o `README-ENTREGA.md` e os arquivos desta pasta `uso-de-ia/`.

## O que eu fiz

- Conduzi a sessão, definindo o escopo de cada etapa e aprovando as alterações antes de avançar.
- Revisei o diagnóstico, as correções aplicadas e os resultados dos testes.
- Validei a conferência final contra a amostra do README e a entrega.
- Solicitei a criação de testes adicionais para ampliar a validação do projeto.
- Revisei os novos cenários de teste e os resultados da execução.