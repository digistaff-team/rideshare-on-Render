"""
Тесты для логики маршрутов (route compatibility).
"""
import pytest
from src.bot.handlers import get_city_index, is_route_compatible
from src.config import ROUTE_ORDER


class TestGetCityIndex:
    """Тесты для функции получения индекса города."""

    def test_city_index_krasnodar(self):
        """Краснодар должен быть последним (индекс 8)."""
        idx = get_city_index("Краснодар")
        assert idx == 8

    def test_city_index_skazochniy(self):
        """Сказочный край должен быть первым (индекс 0)."""
        idx = get_city_index("Сказочный край")
        assert idx == 0

    def test_city_index_zdravoe(self):
        idx = get_city_index("Здравое")
        assert idx == 2

    def test_city_index_case_insensitive(self):
        """Поиск должен быть регистронезависимым."""
        assert get_city_index("краснодар") == 8
        assert get_city_index("КРАСНОДАР") == 8
        assert get_city_index("Краснодар") == 8

    def test_city_index_partial_match(self):
        """Должно работать частичное совпадение."""
        assert get_city_index("в Краснодаре") == 8
        assert get_city_index("из Краснодара") == 8

    def test_city_index_not_found(self):
        """Неизвестный город должен возвращать -1."""
        assert get_city_index("Москва") == -1
        assert get_city_index("Неизвестный город") == -1
        assert get_city_index("") == -1


class TestIsRouteCompatible:
    """Тесты для функции совместимости маршрутов."""

    def test_same_direction_compatible(self):
        """Попутчики в одном направлении должны быть совместимы."""
        # Водитель: Краснодар -> Сказочный край (8 -> 0)
        # Пассажир: Краснодар -> Здравое (8 -> 2)
        assert is_route_compatible(
            "Краснодар", "Сказочный край",
            "Краснодар", "Здравое"
        ) is True

    def test_opposite_direction_incompatible(self):
        """Противоположные направления не должны быть совместимы."""
        # Водитель: Краснодар -> Сказочный край (8 -> 0, на север)
        # Пассажир: Здравое -> Краснодар (2 -> 8, на юг)
        assert is_route_compatible(
            "Краснодар", "Сказочный край",
            "Здравое", "Краснодар"
        ) is False

    def test_passenger_within_driver_route(self):
        """Пассажир должен быть в пределах маршрута водителя."""
        # Водитель: Сказочный край -> Краснодар (0 -> 8)
        # Пассажир: Здравое -> Афипский (2 -> 5) - внутри маршрута
        assert is_route_compatible(
            "Сказочный край", "Краснодар",
            "Здравое", "Афипский"
        ) is True

    def test_passenger_outside_driver_route(self):
        """Пассажир вне маршрута водителя не должен быть совместим."""
        # Водитель: Здравое -> Краснодар (2 -> 8)
        # Пассажир: Сказочный край -> Здравое (0 -> 2) - вне маршрута
        assert is_route_compatible(
            "Здравое", "Краснодар",
            "Сказочный край", "Здравое"
        ) is False

    def test_exact_match(self):
        """Точное совпадение маршрутов должно быть совместимо."""
        assert is_route_compatible(
            "Краснодар", "Сказочный край",
            "Краснодар", "Сказочный край"
        ) is True

    def test_unknown_cities(self):
        """Маршруты с неизвестными городами проверяются по вхождению."""
        # Неизвестные города проверяются через string containment
        result = is_route_compatible(
            "Москва", "Питер",
            "Москва", "Питер"
        )
        assert result is True  # Точное совпадение строк

    def test_partial_city_names(self):
        """Частичные названия городов должны работать."""
        assert is_route_compatible(
            "в Краснодаре", "Сказочный",
            "Краснодар", "Сказочный край"
        ) is True
