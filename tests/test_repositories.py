"""Testes dos repositórios de leitura de CSV.

Cobrem arquivos ausentes, colunas faltando, taxas inválidas e os cenários de
borda da normalização da tabela de câmbio.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from onfly_report.exceptions import InputFileError
from onfly_report.repositories.csv_rate_repository import CsvRateRepository
from onfly_report.repositories.csv_reservation_repository import CsvReservationRepository

RESERVATION_HEADER = (
    "reservation_id,traveler_name,company_id,hotel_id,hotel_name,city,country,"
    "checkin_date,checkout_date,rooms,status,currency,amount,payment_method,booked_at\n"
)
RESERVATION_ROW = (
    "R-1,Fulano,EMP-1,H01,Hotel X,Sao Paulo,BR,2025-01-10,2025-01-11,1,"
    "CONFIRMED,BRL,100.00,CARD,2025-01-01T10:00:00-03:00\n"
)


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# CsvReservationRepository
# --------------------------------------------------------------------------- #
class TestReservationRepository:
    def test_missing_file_raises_input_file_error(self, tmp_path):
        repo = CsvReservationRepository(tmp_path / "nao_existe.csv")
        with pytest.raises(InputFileError, match="não encontrado"):
            repo.read()

    def test_missing_required_columns_raises(self, tmp_path):
        path = _write(tmp_path / "r.csv", "reservation_id,amount\nR-1,100.00\n")
        repo = CsvReservationRepository(path)
        with pytest.raises(InputFileError, match="colunas obrigatórias ausentes"):
            repo.read()

    def test_reads_all_rows_without_truncation(self, tmp_path):
        # Garante que o antigo limite de 200 linhas não voltou.
        rows_text = "".join(
            RESERVATION_ROW.replace("R-1", f"R-{i}") for i in range(250)
        )
        path = _write(tmp_path / "r.csv", RESERVATION_HEADER + rows_text)
        rows = CsvReservationRepository(path).read()
        assert len(rows) == 250

    def test_empty_file_with_header_returns_no_rows(self, tmp_path):
        path = _write(tmp_path / "r.csv", RESERVATION_HEADER)
        assert CsvReservationRepository(path).read() == []

    def test_line_number_is_tracked(self, tmp_path):
        path = _write(tmp_path / "r.csv", RESERVATION_HEADER + RESERVATION_ROW)
        rows = CsvReservationRepository(path).read()
        # Cabeçalho na linha 1, primeira reserva na linha 2.
        assert rows[0].line_number == 2


# --------------------------------------------------------------------------- #
# CsvRateRepository
# --------------------------------------------------------------------------- #
class TestRateRepository:
    def test_missing_file_raises(self, tmp_path):
        repo = CsvRateRepository(tmp_path / "sem_taxas.csv")
        with pytest.raises(InputFileError, match="não encontrada"):
            repo.read()

    def test_missing_columns_raises(self, tmp_path):
        path = _write(tmp_path / "t.csv", "currency\nBRL\n")
        with pytest.raises(InputFileError, match="colunas obrigatórias ausentes"):
            CsvRateRepository(path).read()

    def test_empty_table_raises(self, tmp_path):
        path = _write(tmp_path / "t.csv", "currency,rate_to_brl\n")
        with pytest.raises(InputFileError, match="vazia"):
            CsvRateRepository(path).read()

    def test_invalid_rate_raises(self, tmp_path):
        path = _write(tmp_path / "t.csv", "currency,rate_to_brl\nUSD,abc\n")
        with pytest.raises(InputFileError, match="taxa inválida"):
            CsvRateRepository(path).read()

    @pytest.mark.parametrize("rate", ["0", "-1.5", "0.000000"])
    def test_non_positive_rate_raises(self, tmp_path, rate):
        path = _write(tmp_path / "t.csv", f"currency,rate_to_brl\nUSD,{rate}\n")
        with pytest.raises(InputFileError, match="não positiva"):
            CsvRateRepository(path).read()

    def test_incomplete_line_raises(self, tmp_path):
        path = _write(tmp_path / "t.csv", "currency,rate_to_brl\nUSD,\n")
        with pytest.raises(InputFileError, match="incompleta"):
            CsvRateRepository(path).read()

    def test_currency_is_normalized_to_upper(self, tmp_path):
        path = _write(tmp_path / "t.csv", "currency,rate_to_brl\n usd ,5.42\n")
        rates = CsvRateRepository(path).read()
        assert rates == {"USD": Decimal("5.42")}
