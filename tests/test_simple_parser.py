"""
Тесты для простого парсера (SimpleParser).
"""
import pytest
from datetime import date
from src.services.simple_parser import SimpleParser


class TestSimpleParserCities:
    """Тесты парсинга городов."""

    def setup_method(self):
        self.parser = SimpleParser()

    def test_parse_from_to_cities(self):
        """Парсинг маршрута с предлогами из/в."""
        result = self.parser.parse("Из Краснодара в Сказочный край")
        assert result is not None
        assert result["origin"] == "Краснодар"
        assert result["destination"] == "Сказочный край"

    def test_parse_zdravoe_to_krasnodar(self):
        result = self.parser.parse("Из Здравого в Краснодар")
        assert result is not None
        assert result["origin"] == "Здравое"
        assert result["destination"] == "Краснодар"

    def test_parse_gregorievskaya(self):
        result = self.parser.parse("Из Григорьевской в Энем")
        assert result is not None
        assert result["origin"] == "Григорьевская"
        assert result["destination"] == "Энем"

    def test_parse_afipskiy(self):
        result = self.parser.parse("От Афипского до Яблоновского")
        assert result is not None
        assert result["origin"] == "Афипский"
        assert result["destination"] == "Яблоновский"


class TestSimpleParserDate:
    """Тесты парсинга даты."""

    def setup_method(self):
        self.parser = SimpleParser()

    def test_parse_date_today(self):
        result = self.parser.parse("поездка сегодня")
        assert result is not None
        assert result["date"] == date.today().strftime("%Y-%m-%d")

    def test_parse_date_tomorrow(self):
        from datetime import timedelta
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        result = self.parser.parse("поездка завтра")
        assert result is not None
        assert result["date"] == tomorrow

    def test_parse_date_day_after_tomorrow(self):
        from datetime import timedelta
        day_after = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")
        result = self.parser.parse("послезавтра")
        assert result is not None
        assert result["date"] == day_after


class TestSimpleParserTime:
    """Тесты парсинга времени."""

    def setup_method(self):
        self.parser = SimpleParser()

    def test_parse_time_format_hhmm(self):
        result = self.parser.parse("в 10:00")
        assert result is not None
        assert result["start_time"] == "10:00"

    def test_parse_time_morning(self):
        result = self.parser.parse("в 9 утра")
        assert result is not None
        assert result["start_time"] == "09:00"

    def test_parse_time_evening(self):
        result = self.parser.parse("в 9 вечера")
        assert result is not None
        assert result["start_time"] == "21:00"

    def test_parse_time_hours_format(self):
        result = self.parser.parse("в 14 часов")
        assert result is not None
        assert result["start_time"] == "14:00"


class TestSimpleParserSeats:
    """Тесты парсинга количества мест."""

    def setup_method(self):
        self.parser = SimpleParser()

    def test_parse_seats_digit(self):
        result = self.parser.parse("есть 3 места")
        assert result is not None
        assert result["seats"] == 3

    def test_parse_seats_word_one(self):
        result = self.parser.parse("одно место")
        assert result is not None
        assert result["seats"] == 1

    def test_parse_seats_word_two(self):
        result = self.parser.parse("два места")
        assert result is not None
        assert result["seats"] == 2

    def test_parse_seats_word_three(self):
        result = self.parser.parse("три места")
        assert result is not None
        assert result["seats"] == 3


class TestSimpleParserFull:
    """Тесты полного парсинга сообщения."""

    def setup_method(self):
        self.parser = SimpleParser()

    def test_parse_full_message_driver(self):
        result = self.parser.parse(
            "Из Краснодара в Сказочный край завтра в 10 утра, есть 2 места",
            role="driver"
        )
        assert result is not None
        assert result["origin"] == "Краснодар"
        assert result["destination"] == "Сказочный край"
        assert "date" in result
        assert result["start_time"] == "10:00"
        assert result["seats"] == 2

    def test_parse_full_message_passenger(self):
        result = self.parser.parse(
            "Из Здравого в Краснодар сегодня в 18:00, нужно одно место",
            role="passenger"
        )
        assert result is not None
        assert result["origin"] == "Здравое"
        assert result["destination"] == "Краснодар"
        assert "date" in result
        assert result["start_time"] == "18:00"
        assert result["seats"] == 1
