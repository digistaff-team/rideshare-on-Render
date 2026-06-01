import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SimpleParser:
    """Простой fallback-парсер для извлечения данных о поездках"""
    
    def __init__(self):
        # Базовые формы городов (будем искать по корню)
        self.cities = [
            "здрав", "григорьевск", "смоленск", "афипск", "энем", "яблоновск",
            "краснодар", "кореновск", "усть-лабинск", "динск", "ростов",
            "сказочн", "живой", "северск"
        ]
        # Полные названия для вывода
        self.cities_full = {
            "здрав": "Здравое",
            "григорьевск": "Григорьевская",
            "смоленск": "Смоленская",
            "афипск": "Афипский",
            "энем": "Энем",
            "яблоновск": "Яблоновский",
            "краснодар": "Краснодар",
            "кореновск": "Кореновск",
            "усть-лабинск": "Усть-Лабинск",
            "динск": "Динская",
            "ростов": "Ростов",
            "сказочн": "Сказочный край",
            "живой": "Живой дом",
            "северск": "Северская",
        }
    
    def parse(self, text: str, role: str = None):
        """Парсит текст и возвращает словарь с данными о поездке"""
        logger.info(f"🔍 SimpleParser: парсинг текста '{text[:50]}...'")
        
        result = {}
        text_lower = text.lower()
        
        # 1. Парсинг городов (откуда/куда)
        origin, destination = self._parse_cities(text_lower)
        if origin:
            result["origin"] = origin
        if destination:
            result["destination"] = destination
        
        # 2. Парсинг даты
        date = self._parse_date(text_lower)
        if date:
            result["date"] = date
        
        # 3. Парсинг времени
        time = self._parse_time(text_lower)
        if time:
            result["start_time"] = time
        
        # 4. Парсинг количества мест
        seats = self._extract_seats(text_lower)
        if seats is not None:
            result["seats"] = seats
        
        if result:
            logger.info(
                f"✅ SimpleParser: {result.get('origin', '?')} → {result.get('destination', '?')}, "
                f"дата={result.get('date', '?')}, время={result.get('starttime', '?')}, "
                f"мест={result.get('seats', '?')}"
            )
        else:
            logger.warning("⚠️ SimpleParser: не смог извлечь данные")
        
        return result if result else None
    
    def _parse_cities(self, text: str):
        """Извлекает города отправления и назначения (учитывает падежи)"""
        origin = None
        destination = None
        
        # Паттерны для "откуда" (родительный падеж)
        origin_match = re.search(r"(?:из|с|от)\s+(\w+)", text)
        if origin_match:
            city_word = origin_match.group(1)
            # Ищем по корню слова
            for city_root, city_name in self.cities_full.items():
                if city_root in city_word:
                    origin = city_name
                    break
        
        # Паттерны для "куда" (винительный падеж)
        dest_match = re.search(r"(?:в|до)\s+(\w+)", text)
        if dest_match:
            city_word = dest_match.group(1)
            # Ищем по корню слова
            for city_root, city_name in self.cities_full.items():
                if city_root in city_word and city_name != origin:
                    destination = city_name
                    break
        
        return origin, destination
    
    def _parse_date(self, text: str):
        """Извлекает дату из текста"""
        today = datetime.now().date()
        
        if "послезавтра" in text:
            return (today + timedelta(days=2)).strftime("%Y-%m-%d")

        if "завтра" in text:
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")

        if "сегодня" in text:
            return today.strftime("%Y-%m-%d")
        
        # Паттерн для конкретных дат
        date_match = re.search(r"(\d{1,2})[.\-/](\d{1,2})", text)
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year = today.year
            try:
                target_date = datetime(year, month, day).date()
                return target_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        return None
    
    def _parse_time(self, text: str):
        """Извлекает время из текста"""
        patterns = [
            r"(\d{1,2}):(\d{2})",           # 10:00
            r"в\s+(\d{1,2})\s*(?:часов?)?", # в 10 часов
            r"(\d{1,2})\s*(?:утра|вечера)", # 10 утра
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                hour = int(match.group(1))
                minute = match.group(2) if len(match.groups()) > 1 and match.group(2) else "00"
                
                # Корректировка AM/PM
                if "вечера" in text and hour < 12:
                    hour += 12
                
                if isinstance(minute, str) and minute.isdigit():
                    return f"{hour:02d}:{minute}"
                else:
                    return f"{hour:02d}:00"
        
        return None
    
    def _extract_seats(self, text: str):
        """Извлекает количество мест из текста"""
        numbers_map = {
            "одно": 1, "один": 1, "одна": 1,
            "два": 2, "две": 2,
            "три": 3,
            "четыре": 4,
            "пять": 5,
        }
        
        patterns = [
            (r"(\d+)\s*мест", "digit"),
            (r"есть\s+(\d+)", "digit"),
            (r"(одно|один|два|две|три|четыре|пять)\s+мест", "word"),
            (r"есть\s+(одно|один|два|две|три|четыре|пять)", "word"),
        ]
        
        for pattern, match_type in patterns:
            match = re.search(pattern, text)
            if match:
                num_str = match.group(1)
                
                if match_type == "digit" and num_str.isdigit():
                    return int(num_str)
                
                elif match_type == "word" and num_str in numbers_map:
                    return numbers_map[num_str]
        
        if re.search(r"есть\s+место|одно\s+место", text):
            return 1
        
        return None
