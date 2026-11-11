"""Testes de integração entre módulos.

Exercitam o ReportBuilder com repositórios reais (lendo CSVs em disco), cobrindo
agregação por mês, ranking com empate, arredondamento half-up, relatório vazio e
o parser de linhas, para garantir que as peças se encaixam de ponta a ponta.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from onfly_report.exceptions import InputFileError
from onfly_report.models import RawRow
from onfly_report.repositories.csv_rate_repository import CsvRateRepository
from onfly_report.repositories.csv_reservation_repository import CsvReservationRepository
from onfly_report.services.report_builder import ReportBuilder, format_money
from onfly_report.services.row_parser import RowParser

HEADER = (
    "reservation_id,traveler_name,company_id,hotel_id,hotel_name,city,country,"
    "checkin_date,checkout_date,rooms,status,currency,amount,payment_method,booked_at\n"
)
RATES = "currency,rate_to_brl\nBRL,1.000000\nUSD,5.420000\nEUR,5.880000\n"


def _row(
    rid="R-1",
    hotel_id="H01",
    hotel_name="Hotel X",
    checkin="2025-01-10",
    checkout="2025-01-11",
    rooms="1",
    status="CONFIRMED",
    currency="BRL",
    amount="100.00",
) -> str:
    return (
        f"{rid},Fulano,EMP-1,{hotel_id},{hotel_name},Sao Paulo,BR,"
        f"{checkin},{checkout},{rooms},{status},{currency},{amount},CARD,"
        "2025-01-01T10:00:00-03:00\n"
    )


def _build(tmp_path: Path, rows: list[str], top_n: int = 5) -> dict:
    input_path = tmp_path / "reservas.csv"
    rates_path = tmp_path / "rates.csv"
    input_path.write_text(HEADER + "".join(rows), encoding="utf-8")
    rates_path.write_text(RATES, encoding="utf-8")
    return ReportBuilder(
        reservation_repository=CsvReservationRepository(input_path),
        rate_repository=CsvRateRepository(rates_path),
        top_n=top_n,
    ).build()


# --------------------------------------------------------------------------- #
# format_money (serialização half-up)
# --------------------------------------------------------------------------- #
class TestFormatMoney:
    def test_two_decimal_places(self):
        assert format_money(Decimal("1234.5")) == "1234.50"

    def test_half_up_rounds_up(self):
        assert format_money(Decimal("1.005")) == "1.01"

    def test_half_up_on_boundary(self):
        assert format_money(Decimal("2.675")) == "2.68"

    def test_no_thousand_separator(self):
        assert format_money(Decimal("1000000")) == "1000000.00"


# --------------------------------------------------------------------------- #
# Relatório vazio
# --------------------------------------------------------------------------- #
def test_empty_report_has_zeroed_summary(tmp_path):
    report = _build(tmp_path, rows=[])
    summary = report["summary"]
    assert summary["total_reservations"] == 0
    assert summary["total_room_nights"] == 0
    assert summary["total_amount_brl"] == "0.00"
    assert summary["average_nightly_rate_brl"] == "0.00"
    assert report["by_month"] == []
    assert report["top_hotels"] == []


def test_only_cancelled_yields_zero_financials(tmp_path):
    report = _build(
        tmp_path,
        rows=[
            _row(rid="R-1", status="CANCELLED", amount="500.00"),
            _row(rid="R-2", status="NO_SHOW", amount="300.00"),
        ],
    )
    summary = report["summary"]
    assert summary["total_reservations"] == 2
    assert summary["confirmed_reservations"] == 0
    assert summary["total_amount_brl"] == "0.00"
    assert summary["average_nightly_rate_brl"] == "0.00"
    assert report["top_hotels"] == []


# --------------------------------------------------------------------------- #
# Agregação por mês
# --------------------------------------------------------------------------- #
def test_by_month_groups_and_sorts_ascending(tmp_path):
    report = _build(
        tmp_path,
        rows=[
            _row(rid="R-1", checkin="2025-02-01", checkout="2025-02-03"),
            _row(rid="R-2", checkin="2025-01-10", checkout="2025-01-12"),
            _row(rid="R-3", checkin="2025-01-20", checkout="2025-01-21"),
        ],
    )
    months = [m["month"] for m in report["by_month"]]
    assert months == ["2025-01", "2025-02"]
    jan = report["by_month"][0]
    assert jan["reservations"] == 2
    assert jan["room_nights"] == 3  # 2 + 1


def test_by_month_uses_checkin_month_not_checkout(tmp_path):
    # Check-in em janeiro, check-out em fevereiro -> conta em 2025-01.
    report = _build(
        tmp_path,
        rows=[_row(checkin="2025-01-30", checkout="2025-02-02")],
    )
    assert [m["month"] for m in report["by_month"]] == ["2025-01"]


# --------------------------------------------------------------------------- #
# Ranking de hotéis
# --------------------------------------------------------------------------- #
def test_top_hotels_tiebreak_by_hotel_id_ascending(tmp_path):
    # Mesmo valor: desempata por hotel_id crescente.
    report = _build(
        tmp_path,
        rows=[
            _row(rid="R-1", hotel_id="H03", amount="500.00"),
            _row(rid="R-2", hotel_id="H01", amount="500.00"),
            _row(rid="R-3", hotel_id="H02", amount="500.00"),
        ],
    )
    assert [h["hotel_id"] for h in report["top_hotels"]] == ["H01", "H02", "H03"]


def test_top_n_limits_number_of_hotels(tmp_path):
    report = _build(
        tmp_path,
        rows=[_row(rid=f"R-{i}", hotel_id=f"H{i:02d}", amount=f"{100 * i}.00") for i in range(1, 6)],
        top_n=2,
    )
    assert len(report["top_hotels"]) == 2


def test_same_hotel_across_rows_is_aggregated(tmp_path):
    report = _build(
        tmp_path,
        rows=[
            _row(rid="R-1", hotel_id="H01", amount="300.00", checkout="2025-01-12"),
            _row(rid="R-2", hotel_id="H01", amount="200.00", checkout="2025-01-13"),
        ],
    )
    assert len(report["top_hotels"]) == 1
    hotel = report["top_hotels"][0]
    assert hotel["hotel_id"] == "H01"
    assert hotel["total_brl"] == "500.00"
    assert hotel["room_nights"] == 2 + 3


# --------------------------------------------------------------------------- #
# Câmbio dentro do pipeline + exatidão
# --------------------------------------------------------------------------- #
def test_mixed_currencies_totaled_in_brl(tmp_path):
    report = _build(
        tmp_path,
        rows=[
            _row(rid="R-1", currency="BRL", amount="100.00"),
            _row(rid="R-2", currency="USD", amount="100.00"),
            _row(rid="R-3", currency="EUR", amount="100.00"),
        ],
    )
    # 100 + 542 + 588 = 1230
    assert report["summary"]["total_amount_brl"] == "1230.00"


def test_average_nightly_rate(tmp_path):
    report = _build(
        tmp_path,
        rows=[_row(checkin="2025-01-10", checkout="2025-01-14", amount="400.00")],
    )
    # 400 BRL / 4 noites = 100.00
    assert report["summary"]["average_nightly_rate_brl"] == "100.00"


# --------------------------------------------------------------------------- #
# RowParser
# --------------------------------------------------------------------------- #
class TestRowParser:
    def _raw(self, **overrides) -> RawRow:
        base = {
            "reservation_id": "R-1",
            "traveler_name": "Fulano",
            "company_id": "EMP-1",
            "hotel_id": "H01",
            "hotel_name": "Hotel X",
            "city": "Sao Paulo",
            "country": "BR",
            "checkin_date": "2025-01-10",
            "checkout_date": "2025-01-11",
            "rooms": "1",
            "status": "CONFIRMED",
            "currency": "BRL",
            "amount": "100.00",
            "payment_method": "CARD",
            "booked_at": "2025-01-01T10:00:00-03:00",
        }
        base.update(overrides)
        return RawRow(line_number=2, values=base)

    def test_parses_valid_row(self):
        reservation = RowParser().parse(self._raw())
        assert reservation.amount == Decimal("100.00")
        assert reservation.rooms == 1
        assert reservation.checkin.isoformat() == "2025-01-10"

    def test_strips_whitespace(self):
        reservation = RowParser().parse(self._raw(hotel_id="  H09  "))
        assert reservation.hotel_id == "H09"

    def test_invalid_amount_raises_input_file_error(self):
        with pytest.raises(InputFileError, match="linha 2"):
            RowParser().parse(self._raw(amount="abc"))

    def test_invalid_rooms_raises_input_file_error(self):
        with pytest.raises(InputFileError, match="linha 2"):
            RowParser().parse(self._raw(rooms="dois"))

    def test_invalid_date_raises_input_file_error(self):
        with pytest.raises(InputFileError, match="linha 2"):
            RowParser().parse(self._raw(checkin_date="10/01/2025"))
