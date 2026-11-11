"""Testes unitários adicionais dos serviços de domínio.

Cobrem casos extremos e limites das funções puras de cálculo, conversão e
política de status, isolando cada módulo do restante do pipeline.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from onfly_report.services.currency_converter import convert_to_brl
from onfly_report.services.status_policy import is_billable
from onfly_report.services.stay_calculator import calculate_room_nights


# --------------------------------------------------------------------------- #
# stay_calculator
# --------------------------------------------------------------------------- #
class TestCalculateRoomNights:
    def test_single_night_single_room(self):
        assert calculate_room_nights(date(2025, 1, 10), date(2025, 1, 11), 1) == 1

    def test_multiple_rooms_multiply_nights(self):
        # 3 noites * 4 quartos
        assert calculate_room_nights(date(2025, 1, 10), date(2025, 1, 13), 4) == 12

    def test_month_boundary(self):
        assert calculate_room_nights(date(2025, 1, 30), date(2025, 2, 2), 1) == 3

    def test_year_boundary(self):
        assert calculate_room_nights(date(2024, 12, 31), date(2025, 1, 2), 1) == 2

    def test_leap_year_february(self):
        # 2024 é bissexto: 28/02 -> 01/03 são 2 noites
        assert calculate_room_nights(date(2024, 2, 28), date(2024, 3, 1), 1) == 2

    def test_long_stay(self):
        assert calculate_room_nights(date(2025, 1, 1), date(2025, 12, 31), 1) == 364


# --------------------------------------------------------------------------- #
# currency_converter
# --------------------------------------------------------------------------- #
RATES = {"BRL": Decimal("1.000000"), "USD": Decimal("5.420000"), "EUR": Decimal("5.880000")}


class TestConvertToBrl:
    def test_brl_is_identity(self):
        assert convert_to_brl(Decimal("100.00"), "BRL", RATES) == Decimal("100.000000")

    def test_usd_multiplies_by_rate(self):
        assert convert_to_brl(Decimal("100.00"), "USD", RATES) == Decimal("542.000000")

    def test_eur_multiplies_by_rate(self):
        assert convert_to_brl(Decimal("150.00"), "EUR", RATES) == Decimal("882.000000")

    def test_result_is_decimal_not_float(self):
        result = convert_to_brl(Decimal("10.00"), "USD", RATES)
        assert isinstance(result, Decimal)

    def test_preserves_precision_without_float_rounding(self):
        # 0.1 + 0.2 em float daria 0.30000000000000004; em Decimal deve ser exato.
        result = convert_to_brl(Decimal("0.10"), "BRL", RATES) + convert_to_brl(
            Decimal("0.20"), "BRL", RATES
        )
        assert result == Decimal("0.30")

    def test_zero_amount(self):
        assert convert_to_brl(Decimal("0.00"), "USD", RATES) == Decimal("0.000000")

    def test_unknown_currency_raises_keyerror(self):
        with pytest.raises(KeyError):
            convert_to_brl(Decimal("10.00"), "JPY", RATES)


# --------------------------------------------------------------------------- #
# status_policy
# --------------------------------------------------------------------------- #
class TestStatusPolicy:
    def test_confirmed_is_billable(self):
        assert is_billable("CONFIRMED") is True

    @pytest.mark.parametrize("status", ["CANCELLED", "NO_SHOW"])
    def test_non_confirmed_is_not_billable(self, status):
        assert is_billable(status) is False

    @pytest.mark.parametrize("status", ["", "confirmed", "PENDING", "CONFIRMED "])
    def test_unexpected_values_are_not_billable(self, status):
        # Apenas o valor canônico exato conta; variações não são faturáveis.
        assert is_billable(status) is False
