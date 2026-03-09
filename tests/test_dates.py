"""
Тесты для функций парсинга и форматирования дат.
"""
import pytest
from datetime import datetime, date
from src.bot.handlers import parse_date, fmt_date


class TestParseDate:
    """Тесты для функции парсинга даты."""

    def test_parse_date_iso_format(self):
        """Парсинг ISO формата YYYY-MM-DD."""
        result = parse_date("2024-03-15")
        assert result == date(2024, 3, 15)

    def test_parse_date_ddmmyyyy(self):
        """Парсинг формата DD.MM.YYYY."""
        result = parse_date("15.03.2024")
        assert result == date(2024, 3, 15)

    def test_parse_date_ddmmyy(self):
        """Парсинг формата DD.MM.YY."""
        result = parse_date("15.03.24")
        assert result == date(2024, 3, 15)

    def test_parse_date_ddmmyyyy_with_dashes(self):
        """Парсинг формата DD-MM-YYYY."""
        result = parse_date("15-03-2024")
        assert result == date(2024, 3, 15)

    def test_parse_date_invalid(self):
        """Неверный формат даты должен возвращать None."""
        assert parse_date("invalid") is None
        assert parse_date("") is None
        assert parse_date("32.13.2024") is None

    def test_parse_date_single_digit(self):
        """Даты с одной цифрой должны парситься."""
        result = parse_date("1.1.2024")
        assert result == date(2024, 1, 1)


class TestFmtDate:
    """Тесты для функции форматирования даты."""

    def test_fmt_date_date_object(self):
        """Форматирование date объекта."""
        d = date(2024, 3, 15)
        assert fmt_date(d) == "15.03.2024"

    def test_fmt_date_none(self):
        """None должен возвращать пустую строку."""
        assert fmt_date(None) == ""

    def test_fmt_date_empty(self):
        """Пустое значение должно возвращать пустую строку."""
        assert fmt_date("") == ""

    def test_fmt_date_string_ddmmyyyy(self):
        """Форматирование строки DD.MM.YYYY."""
        assert fmt_date("2024-03-15") == "15.03.2024"

    def test_fmt_date_already_formatted(self):
        """Уже отформатированная дата должна возвращаться как есть."""
        assert fmt_date("15.03.2024") == "15.03.2024"

    def test_fmt_date_invalid_string(self):
        """Неверная строка должна возвращаться как есть."""
        assert fmt_date("invalid") == "invalid"


class TestDateHelpers:
    """Тесты для вспомогательных функций работы с датой."""

    def test_today_date(self):
        """Тест текущей даты."""
        today = datetime.now().date()
        assert fmt_date(today) == today.strftime("%d.%m.%Y")

    def test_date_range(self):
        """Тест диапазона дат."""
        from datetime import timedelta
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        assert tomorrow > today
        assert fmt_date(tomorrow) == tomorrow.strftime("%d.%m.%Y")
