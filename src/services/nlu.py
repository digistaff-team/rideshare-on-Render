import aiohttp
import logging
import json
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Системный промпт вынесен в константу
SYSTEM_PROMPT_TEMPLATE = """Ты — Везучий, умный помощник сервиса попутчиков. Твоя цель — помочь пользователю создать заявку на поездку (водитель или пассажир).

Ты общаешься в естественном человечном стиле, вежливо и заботливо, обращаешься к пользователю на "вы", используешь обращение по имени, если оно указано в заметках к диалогу.

Сегодня {current_date}

ПОВЕДЕНИЕ В ДИАЛОГЕ:
Если пользователь просто общается (приветствие, 'как дела', любые вопросы), отвечай вежливо и поддерживай диалог.
Если пользователь пишет о поездке, мягко уточняй недостающие данные (откуда, куда, дата, время, места).
Если пользователь - водитель, уточняй, сколько есть свободных мест в машине для пассажиров.
Если пользователь - пассажир, уточняй, сколько свободных мест нужно в машине для пассажиров.
Если пользователь — пассажир, НЕ требуй от него точного времени выезда. Если он не назвал время, вставь в поле `start_time` значение null.

ФОРМАТ ОТВЕТА:
Когда ты собрал все данные, напиши пользователю короткое вежливое заключение и только ПОСЛЕ этого в самом конце сообщения выведи JSON:

{{
  "origin": "город_откуда",
  "destination": "город_куда",
  "date": "DD.MM.YYYY",
  "start_time": "HH:MM",
  "seats": 1
}}

СПРАВОЧНИК ГОРОДОВ (Пиши ТОЛЬКО эти названия):
Здравое, Григорьевская, Сказочный край, Живой дом, Смоленская, Ставропольская, Северская, Афипский, Энем, Яблоновский, Краснодар, Ж/д вокзал Краснодар, Аэропорт Краснодар.

ПРАВИЛА ФОРМАТИРОВАНИЯ ДАННЫХ:
1. 'origin' и 'destination': СТРОГО в именительном падеже из справочника.
2. 'date': Формат DD.MM.YYYY. Если "завтра" или "послезавтра", вычисли от {current_date}.
3. 'start_time': Формат HH:MM. Если время не указано пассажиром, поставь null.
4. 'seats': Формат integer, целое число.
5. Никогда не смешивай JSON с текстом, всегда выводи его в конце сообщения.
6. Не отправляй JSON, пока не соберешь всю необходимую информацию.
7. Различай утреннее и вечернее время: "9 утра" -> "09:00", "9 вечера" -> "21:00".

Если данных еще не хватает (Откуда, Куда, Дата), отвечай только текстом, задавай уточняющие вопросы. НЕ присылай JSON."""


class NLUProcessor:
    def __init__(self):
        # Используем переменные окружения PROTALK_*
        self.api_token = os.getenv("PROTALK_TOKEN")
        self.bot_id = os.getenv("PROTALK_BOT_ID")
        self.base_url = "https://api.pro-talk.ru/api/v1.0/ask"

    async def parse_intent(self, text: str, user_id: int, role: str = None) -> dict:
        """
        Отправляет текст в Pro-Talk API и извлекает JSON с деталями поездки.
        
        Args:
            text: Текст сообщения от пользователя
            user_id: Telegram ID пользователя
            role: "driver" или "passenger"
        
        Returns:
            dict с данными поездки или {"raw_text": "ответ бота"}
        """
        if not self.api_token or not self.bot_id:
            logger.error("❌ PROTALK_TOKEN or PROTALK_BOT_ID missing in .env")
            return {"raw_text": "⚠️ Сервис временно недоступен. Попробуйте позже."}

        # Формируем системный промпт
        current_date = datetime.now().strftime("%d.%m.%Y")
        system_instruction = SYSTEM_PROMPT_TEMPLATE.format(current_date=current_date)

        # Добавляем контекст роли
        context_prefix = ""
        if role == "driver":
            context_prefix = "\n[Роль пользователя: Водитель. Он хочет ОПУБЛИКОВАТЬ поездку. Извлеки JSON: origin, destination, date, time, seats.]"
        elif role == "passenger":
            context_prefix = "\n[Роль пользователя: Пассажир. Он хочет НАЙТИ машину. Извлеки JSON: origin, destination, date, time, seats.]"

        # Собираем полное сообщение
        full_message = f"{system_instruction}\n{context_prefix}\nСообщение пользователя: {text}"

        url = f"{self.base_url}/{self.api_token}"
        
        # Валидируем bot_id перед использованием
        try:
            bot_id_int = int(self.bot_id)
        except (ValueError, TypeError):
            logger.error("❌ Invalid PROTALK_BOT_ID: must be an integer")
            return {"raw_text": "⚠️ Ошибка конфигурации бота. Обратитесь к администратору."}
        
        payload = {
            "bot_id": bot_id_int,
            "chat_id": str(user_id),
            "message": full_message
        }

        try:
            # Добавлен timeout
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    resp_text = await resp.text()
                    
                    if resp.status != 200:
                        logger.error(f"❌ Pro-Talk API Error {resp.status}: {resp_text}")
                        return {}

                    try:
                        api_response = json.loads(resp_text)
                        bot_reply = api_response.get("done", "")
                    except json.JSONDecodeError:
                        logger.error("❌ Failed to decode Pro-Talk response")
                        return {}

            # Ищем JSON в ответе
            json_matches = list(re.finditer(r"\{.*?\}", bot_reply, re.DOTALL))
            result_data = {}
            clean_text = bot_reply

            if json_matches:
                # Берем последний JSON блок
                last_match = json_matches[-1]
                json_str = last_match.group(0)
                
                try:
                    result_data = json.loads(json_str)
                    # Вырезаем JSON из текста
                    clean_text = bot_reply.replace(json_str, "").strip()
                except json.JSONDecodeError:
                    pass

            # Очистка от markdown
            clean_text = re.sub(r"```.*?```", "", clean_text, flags=re.DOTALL).strip()
            clean_text = clean_text.replace("```", "").strip()
            clean_text = re.sub(r"^\s*json\s*", "", clean_text, flags=re.MULTILINE).strip()

            # Конвертируем дату в YYYY-MM-DD для БД (поддержка разных форматов)
            if result_data and "date" in result_data:
                result_data["date"] = self._normalize_date(result_data["date"])

            # Возвращаем результат
            if result_data:
                result_data["raw_text"] = clean_text
                return result_data

            return {"raw_text": clean_text}

        except Exception as e:
            logger.error(f"❌ Exception in parse_intent: {e}")
            return {}

    def _normalize_date(self, date_str: str) -> str:
        """
        Конвертирует дату в формат YYYY-MM-DD.
        Поддерживает форматы: DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD, YYYY/MM/DD
        """
        if not date_str:
            return date_str

        # Пробуем разные форматы
        formats = [
            ("%d.%m.%Y", "DD.MM.YYYY"),
            ("%d/%m/%Y", "DD/MM/YYYY"),
            ("%Y-%m-%d", "YYYY-MM-DD"),
            ("%Y/%m/%d", "YYYY/MM/DD"),
        ]

        for fmt, fmt_name in formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Если ни один формат не подошел, логируем и возвращаем как есть
        logger.warning(f"⚠️ Неверный формат даты: {date_str}")
        return date_str
