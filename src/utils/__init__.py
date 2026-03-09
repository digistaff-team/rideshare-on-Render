"""
Утилиты для парсинга текста и извлечения данных.
"""
import re
from typing import Optional


# Карта слов-чисел в цифры
NUMBERS_MAP = {
    "одно": 1, "один": 1, "одна": 1,
    "два": 2, "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
}


def extract_seats(text: str) -> int:
    """
    Извлекает количество мест из текста сообщения.
    
    Args:
        text: Текст сообщения пользователя
        
    Returns:
        Количество мест (по умолчанию 1)
    """
    text_lower = text.lower()
    
    patterns = [
        (r"(\d+)\s*мест", "digit"),
        (r"есть\s+(\d+)", "digit"),
        (r"(одно|один|одна|два|две|три|четыре|пять)\s+мест", "word"),
        (r"есть\s+(одно|один|одна|два|две|три|четыре|пять)", "word"),
    ]

    for pattern, match_type in patterns:
        match = re.search(pattern, text_lower)
        if match:
            num_str = match.group(1)

            if match_type == "digit" and num_str.isdigit():
                return int(num_str)

            elif match_type == "word" and num_str in NUMBERS_MAP:
                return NUMBERS_MAP[num_str]

    if re.search(r"есть\s+место|одно\s+место", text_lower):
        return 1

    return 1


def validate_city_name(city: str, max_length: int = 100) -> bool:
    """
    Проверяет корректность названия города.
    
    Args:
        city: Название города
        max_length: Максимальная длина
        
    Returns:
        True если название корректно
    """
    if not city or len(city) > max_length:
        return False
    # Разрешаем буквы, цифры, пробелы, дефисы
    return bool(re.match(r'^[\w\s\-]+$', city))


def validate_seats(seats: Optional[int], min_seats: int = 1, max_seats: int = 10) -> int:
    """
    Валидирует и ограничивает количество мест.
    
    Args:
        seats: Количество мест
        min_seats: Минимальное значение
        max_seats: Максимальное значение
        
    Returns:
        Валидированное количество мест
    """
    if seats is None:
        return 1
    return max(min_seats, min(seats, max_seats))
