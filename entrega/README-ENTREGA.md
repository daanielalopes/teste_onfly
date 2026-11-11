# Entrega — Consolidador de reservas de hotel

Este documento descreve os defeitos encontrados no CLI, a causa raiz de cada um, como foram
investigados e corrigidos, como validar e o resultado do `pytest`.

## Defeitos corrigidos

Todos os defeitos estavam na camada de serviços/repositório. Os dados de entrada estavam
consistentes, conforme antecipado pelo enunciado.

### 1. Leitura das reservas truncada em 200 linhas
- **Arquivo:** `src/onfly_report/repositories/csv_reservation_repository.py`
- **Causa raiz:** um `break` interrompia a leitura ao atingir 200 linhas, descartando reservas
  silenciosamente e violando o contrato de `total_reservations`.
- **Correção:** removido o `break`; o arquivo passa a ser lido por completo.

### 2. Conversão de câmbio invertida e usando `float`
- **Arquivo:** `src/onfly_report/services/currency_converter.py`
- **Causa raiz:** o valor era **dividido** pela taxa (`float(amount) / float(rate)`) em vez de
  multiplicado, e ainda convertido para `float`, violando a regra de usar `Decimal` no dinheiro.
- **Correção:** passou a multiplicar em `Decimal` (`amount * rate`).

### 3. Status `NO_SHOW` entrava nos totais financeiros
- **Arquivo:** `src/onfly_report/services/status_policy.py`
- **Causa raiz:** `is_billable` excluía apenas `CANCELLED` (`status != "CANCELLED"`), deixando
  `NO_SHOW` entrar em noites e valores.
- **Correção:** apenas `CONFIRMED` é faturável (`status == "CONFIRMED"`).

### 4. Cálculo de noites usava o dia do mês, não a diferença de datas
- **Arquivo:** `src/onfly_report/services/stay_calculator.py`
- **Causa raiz:** usava `(checkout.day - checkin.day)`, que quebra na virada de mês/ano (ex.: 30/01 a
  02/02 resultava em `-28`).
- **Correção:** usa a diferença real entre as datas (`(checkout - checkin).days`).

### 5. Ranking de hotéis ordenado de forma ascendente
- **Arquivo:** `src/onfly_report/services/report_builder.py`
- **Causa raiz:** a chave de ordenação era `(amount, hotel_id)`, trazendo os hotéis de **menor**
  valor primeiro.
- **Correção:** ordena por valor decrescente e `hotel_id` crescente no empate
  (`key=(-amount, hotel_id)`).

## Como investigou/abordou o problema

1. Leitura completa da arquitetura (CLI, modelos, repositórios e serviços) e do contrato no
   `README.md`, mapeando o fluxo: ler → converter tipos → contar status → filtrar CONFIRMED →
   agregar.
2. Execução do `pytest` para observar as falhas reais e associar cada mensagem de erro a um ponto
   específico do código.
3. Correção pontual de cada defeito na camada responsável, sem alterar o schema, a semântica dos
   campos, os testes fornecidos nem os dados de entrada.
4. Reexecução do `pytest` após cada bloco de correções e validação final contra a amostra do README.

## Como validar

Requisitos: Python 3.11+ e `pytest` (`requirements-dev.txt`).

Rodar os testes:

```bash
PYTHONPATH=src pytest -q
```

Rodar o CLI na amostra de validação e comparar com a tabela do `README.md`:

```bash
PYTHONPATH=src python -m onfly_report \
  --input data/exemplo-validacao.csv \
  --rates data/taxas_cambio.csv \
  --output output/exemplo.json
```

No Windows (PowerShell):

```powershell
$env:PYTHONPATH="src"; python -m onfly_report --input data/exemplo-validacao.csv --rates data/taxas_cambio.csv --output output/exemplo.json
```

### Conferência contra a amostra do README

Todos os campos coincidem com a tabela esperada (`generated_at` é ignorado na comparação):

| Campo | Esperado | Obtido |
|-|-|-|
| `total_reservations` | 12 | 12 |
| `confirmed_reservations` | 9 | 9 |
| `cancelled_reservations` | 2 | 2 |
| `no_show_reservations` | 1 | 1 |
| `total_room_nights` | 28 | 28 |
| `total_amount_brl` | 7566.00 | 7566.00 |
| `average_nightly_rate_brl` | 270.21 | 270.21 |

`by_month` e `top_hotels` também batem integralmente, incluindo a ordem do ranking.

## Resultado do pytest

```
============================= test session starts =============================
platform win32 -- Python 3.11.3, pytest-8.3.4, pluggy-1.7.0
collected 5 items

tests/test_currency.py::test_currency_conversion_to_brl PASSED           [ 20%]
tests/test_nights.py::test_nights_across_month_boundary PASSED           [ 40%]
tests/test_regression_report.py::test_regression_report_on_sample PASSED [ 60%]
tests/test_status_rules.py::test_status_rules_exclude_cancelled_and_no_show PASSED [ 80%]
tests/test_top_hotels.py::test_top_hotels_are_ranked_descending PASSED   [100%]

============================== 5 passed in 1.61s ==============================
```

Os 5 testes fornecidos passam sem qualquer alteração nos próprios testes.
