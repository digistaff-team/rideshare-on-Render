"""
Тесты для модуля утилит (src/utils).
"""
import pytest
from src.utils import extract_seats, validate_city_name, validate_seats


class TestExtractSeats:
    """Тесты для функции извлечения количества мест."""

    def test_extract_seats_digit_one(self):
        assert extract_seats("нужно 1 место") == 1
        assert extract_seats("есть 1 мест") == 1

    def test_extract_seats_digit_two(self):
        assert extract_seats("нужно 2 места") == 2
        assert extract_seats("есть 2 мест") == 2

    def test_extract_seats_digit_three(self):
        assert extract_seats("нужно 3 места") == 3

    def test_extract_seats_digit_four(self):
        assert extract_seats("нужно 4 места") == 4

    def test_extract_seats_digit_five(self):
        assert extract_seats("нужно 5 мест") == 5

    def test_extract_seats_word_one(self):
        assert extract_seats("одно место") == 1
        assert extract_seats("один мест") == 1
        assert extract_seats("одна места") == 1

    def test_extract_seats_word_two(self):
        assert extract_seats("два места") == 2
        assert extract_seats("две места") == 2

    def test_extract_seats_word_three(self):
        assert extract_seats("три места") == 3

    def test_extract_seats_word_four(self):
        assert extract_seats("четыре места") == 4

    def test_extract_seats_word_five(self):
        assert extract_seats("пять мест") == 5

    def test_extract_seats_phrase(self):
        assert extract_seats("есть место") == 1
        assert extract_seats("одно место") == 1

    def test_extract_seats_default(self):
        """По умолчанию возвращается 1 место."""
        assert extract_seats("поездка без указания мест") == 1
        assert extract_seats("") == 1
        assert extract_seats("случайный текст") == 1

    def test_extract_seats_case_insensitive(self):
        assert extract_seats("ОДНО МЕСТО") == 1
        assert extract_seats("ДВА места") == 2


class TestValidateCityName:
    """Тесты для функции валидации названия города."""

    def test_valid_city_names(self):
        assert validate_city_name("Краснодар") is True
        assert validate_city_name("Сказочный край") is True
        assert validate_city_name("Живой дом") is True
        assert validate_city_name("Усть-Лабинск") is True  # с дефисом

    def test_invalid_city_names_empty(self):
        assert validate_city_name("") is False
        assert validate_city_name(None) is False

    def test_invalid_city_names_too_long(self):
        long_name = "A" * 101
        assert validate_city_name(long_name) is False
        assert validate_city_name(long_name, max_length=50) is False

    def test_invalid_city_names_special_chars(self):
        # Некоторые специальные символы недопустимы
        assert validate_city_name("Город@") is False
        assert validate_city_name("Город#") is False

    def test_valid_city_names_with_spaces(self):
        assert validate_city_name("Сказочный край") is True
        assert validate_city_name("Живой дом") is True


class TestValidateSeats:
    """Тесты для функции валидации количества мест."""

    def test_validate_seats_valid(self):
        assert validate_seats(1) == 1
        assert validate_seats(2) == 2
        assert validate_seats(5) == 5

    def test_validate_seats_none(self):
        assert validate_seats(None) == 1

    def test_validate_seats_too_low(self):
        assert validate_seats(0) == 1  # Минимум 1
        assert validate_seats(-1) == 1
        assert validate_seats(-100) == 1

    def test_validate_seats_too_high(self):
        assert validate_seats(11) == 10  # Максимум 10
        assert validate_seats(100) == 10

    def test_validate_seats_custom_limits(self):
        assert validate_seats(0, min_seats=0, max_seats=20) == 0
        assert validate_seats(15, min_seats=0, max_seats=20) == 15
        assert validate_seats(25, min_seats=0, max_seats=20) == 20
