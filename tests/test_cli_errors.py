"""Testes de erro e de contrato do CLI.

Verificam os códigos de saída documentados (0 sucesso, 2 entrada/argumento
inválido, 1 erro inesperado) sem depender do helper fornecido, que sempre
assume sucesso.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

VALID_RATES = "currency,rate_to_brl\nBRL,1.000000\nUSD,5.420000\nEUR,5.880000\n"
HEADER = (
    "reservation_id,traveler_name,company_id,hotel_id,hotel_name,city,country,"
    "checkin_date,checkout_date,rooms,status,currency,amount,payment_method,booked_at\n"
)
VALID_ROW = (
    "R-1,Fulano,EMP-1,H01,Hotel X,Sao Paulo,BR,2025-01-10,2025-01-11,1,"
    "CONFIRMED,BRL,100.00,CARD,2025-01-01T10:00:00-03:00\n"
)


def _env() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + environment.get("PYTHONPATH", "")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run_cli_raw(args: list[str]) -> subprocess.CompletedProcess:
    """Invoca o CLI e devolve o processo cru, sem exigir returncode == 0."""
    return subprocess.run(
        [sys.executable, "-m", "onfly_report", *args],
        cwd=str(PROJECT_ROOT),
        env=_env(),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _make_inputs(tmp_path: Path, rows: str = VALID_ROW, rates: str = VALID_RATES):
    input_path = tmp_path / "reservas.csv"
    rates_path = tmp_path / "rates.csv"
    input_path.write_text(HEADER + rows, encoding="utf-8")
    rates_path.write_text(rates, encoding="utf-8")
    return input_path, rates_path


# --------------------------------------------------------------------------- #
# Argumentos inválidos -> código 2
# --------------------------------------------------------------------------- #
def test_missing_required_arg_exits_2(tmp_path):
    _, rates_path = _make_inputs(tmp_path)
    result = run_cli_raw(["--rates", str(rates_path)])  # falta --input
    assert result.returncode == 2


def test_top_zero_exits_2(tmp_path):
    input_path, rates_path = _make_inputs(tmp_path)
    result = run_cli_raw(
        ["--input", str(input_path), "--rates", str(rates_path), "--top", "0"]
    )
    assert result.returncode == 2


def test_top_negative_exits_2(tmp_path):
    input_path, rates_path = _make_inputs(tmp_path)
    result = run_cli_raw(
        ["--input", str(input_path), "--rates", str(rates_path), "--top", "-3"]
    )
    assert result.returncode == 2


# --------------------------------------------------------------------------- #
# Entrada inválida -> código 2 (InputFileError)
# --------------------------------------------------------------------------- #
def test_missing_input_file_exits_2(tmp_path):
    _, rates_path = _make_inputs(tmp_path)
    result = run_cli_raw(
        ["--input", str(tmp_path / "nao_existe.csv"), "--rates", str(rates_path)]
    )
    assert result.returncode == 2


def test_missing_rates_file_exits_2(tmp_path):
    input_path, _ = _make_inputs(tmp_path)
    result = run_cli_raw(
        ["--input", str(input_path), "--rates", str(tmp_path / "sem_taxas.csv")]
    )
    assert result.returncode == 2


def test_invalid_amount_in_row_exits_2(tmp_path):
    bad_row = VALID_ROW.replace(",100.00,", ",nao-e-numero,")
    input_path, rates_path = _make_inputs(tmp_path, rows=bad_row)
    result = run_cli_raw(["--input", str(input_path), "--rates", str(rates_path)])
    assert result.returncode == 2


def test_invalid_date_in_row_exits_2(tmp_path):
    bad_row = VALID_ROW.replace("2025-01-10", "2025-13-99")
    input_path, rates_path = _make_inputs(tmp_path, rows=bad_row)
    result = run_cli_raw(["--input", str(input_path), "--rates", str(rates_path)])
    assert result.returncode == 2


# --------------------------------------------------------------------------- #
# Sucesso -> código 0
# --------------------------------------------------------------------------- #
def test_valid_run_exits_0_and_writes_output(tmp_path):
    input_path, rates_path = _make_inputs(tmp_path)
    output_path = tmp_path / "report.json"
    result = run_cli_raw(
        [
            "--input", str(input_path),
            "--rates", str(rates_path),
            "--output", str(output_path),
        ]
    )
    assert result.returncode == 0, result.stderr
    assert output_path.exists()


def test_output_directory_is_created(tmp_path):
    input_path, rates_path = _make_inputs(tmp_path)
    output_path = tmp_path / "sub" / "dir" / "report.json"
    result = run_cli_raw(
        [
            "--input", str(input_path),
            "--rates", str(rates_path),
            "--output", str(output_path),
        ]
    )
    assert result.returncode == 0, result.stderr
    assert output_path.exists()
