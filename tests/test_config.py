"""
Тесты для конфигурации и констант.
"""
import pytest
from src import config


class TestConfigConstants:
    """Тесты для констант конфигурации."""

    def test_route_order_exists(self):
        assert hasattr(config, "ROUTE_ORDER")
        assert isinstance(config.ROUTE_ORDER, list)
        assert len(config.ROUTE_ORDER) > 0

    def test_route_order_contains_cities(self):
        expected_cities = ["Краснодар", "Сказочный край", "Здравое"]
        for city in expected_cities:
            assert city in config.ROUTE_ORDER

    def test_route_order_krasnodar_is_last(self):
        """Краснодар должен быть последним в списке."""
        assert config.ROUTE_ORDER[-1] == "Краснодар"

    def test_cleanup_interval(self):
        assert config.CLEANUP_INTERVAL_SECONDS == 3600
        assert config.CLEANUP_DAYS_BACK == 2

    def test_max_rides_limits(self):
        assert config.MAX_RIDES_TO_FETCH == 20
        assert config.MAX_RIDES_TO_DISPLAY == 10

    def test_validation_limits(self):
        assert config.MAX_CITY_NAME_LENGTH == 100
        assert config.MAX_USERNAME_LENGTH == 100
        assert config.MIN_SEATS == 1
        assert config.MAX_SEATS == 10

    def test_timeout_settings(self):
        assert config.API_TIMEOUT_SECONDS == 30
        assert config.DB_POOL_SIZE == 10
        assert config.DB_MAX_OVERFLOW == 20
        assert config.DB_POOL_TIMEOUT == 30
        assert config.DB_POOL_RECYCLE == 1800
