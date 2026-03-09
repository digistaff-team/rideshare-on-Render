"""
Тесты для NLU процессора (Pro-Talk API integration).
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from src.services.nlu import NLUProcessor, SYSTEM_PROMPT_TEMPLATE


class TestNLUProcessorInit:
    """Тесты инициализации NLUProcessor."""

    def test_init_with_env_vars(self, monkeypatch):
        """Инициализация с переменными окружения."""
        monkeypatch.setenv("PROTALK_TOKEN", "test_token")
        monkeypatch.setenv("PROTALK_BOT_ID", "12345")

        processor = NLUProcessor()

        assert processor.api_token == "test_token"
        assert processor.bot_id == "12345"
        assert processor.base_url == "https://api.pro-talk.ru/api/v1.0/ask"

    def test_init_without_env_vars(self, monkeypatch):
        """Инициализация без переменных окружения."""
        monkeypatch.delenv("PROTALK_TOKEN", raising=False)
        monkeypatch.delenv("PROTALK_BOT_ID", raising=False)

        processor = NLUProcessor()

        assert processor.api_token is None
        assert processor.bot_id is None


@pytest.mark.asyncio
class TestNLUProcessorParseIntent:
    """Тесты метода parse_intent."""

    @pytest.fixture
    def processor(self, monkeypatch):
        monkeypatch.setenv("PROTALK_TOKEN", "test_token")
        monkeypatch.setenv("PROTALK_BOT_ID", "12345")
        return NLUProcessor()

    @pytest.fixture
    def mock_api_response(self):
        return {
            "done": '{"origin": "Краснодар", "destination": "Сказочный край", "date": "15.03.2024", "start_time": "10:00", "seats": 2} Ответ бота'
        }

    async def test_parse_intent_success(self, processor, mock_api_response):
        """Успешный парсинг_intent."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=json.dumps(mock_api_response))
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_post.return_value = mock_response

            result = await processor.parse_intent(
                text="Из Краснодара в Сказочный край 15.03.2024 в 10:00, 2 места",
                user_id=123456789,
                role="driver"
            )

            assert result is not None
            assert "origin" in result
            assert result["origin"] == "Краснодар"
            assert result["destination"] == "Сказочный край"

    async def test_parse_intent_missing_credentials(self, monkeypatch):
        """Парсинг без учётных данных."""
        monkeypatch.delenv("PROTALK_TOKEN", raising=False)

        processor = NLUProcessor()
        result = await processor.parse_intent("текст", 123456)

        assert result is not None
        assert "raw_text" in result
        assert "недоступен" in result["raw_text"].lower()

    async def test_parse_intent_api_error(self, processor):
        """Обработка ошибки API."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_post.return_value = mock_response

            result = await processor.parse_intent("текст", 123456)

            assert result == {}

    async def test_parse_intent_invalid_json(self, processor):
        """Обработка невалидного JSON в ответе."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value='{"done": "invalid json {not valid}"}')
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_post.return_value = mock_response

            result = await processor.parse_intent("текст", 123456)

            assert result is not None
            assert "raw_text" in result

    async def test_parse_intent_date_conversion(self, processor, mock_api_response):
        """Конвертация даты из DD.MM.YYYY в YYYY-MM-DD."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=json.dumps({
                "done": '{"origin": "Краснодар", "destination": "Сказочный край", "date": "15.03.2024"}'
            }))
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_post.return_value = mock_response

            result = await processor.parse_intent("текст", 123456)

            assert result["date"] == "2024-03-15"


class TestNormalizeDate:
    """Тесты метода _normalize_date."""

    @pytest.fixture
    def processor(self, monkeypatch):
        monkeypatch.setenv("PROTALK_TOKEN", "test_token")
        monkeypatch.setenv("PROTALK_BOT_ID", "12345")
        return NLUProcessor()

    def test_normalize_date_ddmmyyyy(self, processor):
        result = processor._normalize_date("15.03.2024")
        assert result == "2024-03-15"

    def test_normalize_date_ddmmyyyy_slashes(self, processor):
        result = processor._normalize_date("15/03/2024")
        assert result == "2024-03-15"

    def test_normalize_date_iso_format(self, processor):
        result = processor._normalize_date("2024-03-15")
        assert result == "2024-03-15"

    def test_normalize_date_iso_slashes(self, processor):
        result = processor._normalize_date("2024/03/15")
        assert result == "2024-03-15"

    def test_normalize_date_invalid(self, processor):
        result = processor._normalize_date("invalid")
        assert result == "invalid"

    def test_normalize_date_empty(self, processor):
        result = processor._normalize_date("")
        assert result == ""

    def test_normalize_date_none(self, processor):
        result = processor._normalize_date(None)
        assert result is None
