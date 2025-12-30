import aiohttp
import logging
import json
import os
import re

logger = logging.getLogger(__name__)

class NLUProcessor:
    def __init__(self):
        self.api_token = os.getenv("PROTALK_TOKEN") 
        self.bot_id = os.getenv("PROTALK_BOT_ID")
        self.base_url = "https://api.pro-talk.ru/api/v1.0/ask"

    async def parse_intent(self, text: str, user_id: int, role: str = None) -> dict:
        """
        Отправляет текст в API и пытается извлечь JSON с деталями поездки.
        Аргумент role нужен для правильного контекста (водитель/пассажир).
        """
        if not self.api_token or not self.bot_id:
             logger.error("❌ Tokens missing in Environment Variables")
             return {}

        # --- 1. Формируем контекст для AI ---
        context_prefix = ""
        if role == "driver":
            context_prefix = "[Роль пользователя: Водитель. Он хочет ОПУБЛИКОВАТЬ поездку. Извлеки JSON: origin, destination, date, time, seats.] "
        elif role == "passenger":
            context_prefix = "[Роль пользователя: Пассажир. Он хочет НАЙТИ машину. Извлеки JSON: origin, destination, date, time, seats.] "
            
        full_message = f"{context_prefix}{text}"

        url = f"{self.base_url}/{self.api_token}"
        payload = {
            "bot_id": int(self.bot_id),
            "chat_id": str(user_id),
            "message": full_message
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    resp_text = await resp.text()
                    
                    if resp.status != 200:
                        logger.error(f"❌ API Error {resp.status}: {resp_text}")
                        return {}

                    try:
                        api_response = json.loads(resp_text)
                        # Получаем текстовый ответ от бота
                        bot_reply = api_response.get("done", "")
                    except json.JSONDecodeError:
                        logger.error("❌ Failed to decode API response")
                        return {}

                    # --- 2. Логика поиска JSON в ответе ---
                    
                    # Попытка А: Ищем блок кода Markdown `````` или просто ``````
                    # (?s) включает DOTALL (точка захватывает перенос строки)
                    markdown_match = re.search(r'``````', bot_reply, re.DOTALL)
                    
                    # Попытка Б: Ищем просто JSON объект {...}, если маркдауна нет
                    simple_match = re.search(r'\{.*?\}', bot_reply, re.DOTALL)

                    result_data = {}
                    clean_text = bot_reply
                    found_json_str = None
                    full_match_str = None

                    if markdown_match:
                        found_json_str = markdown_match.group(1) # Содержимое скобок {}
                        full_match_str = markdown_match.group(0) # Весь блок ``````
                    elif simple_match:
                        found_json_str = simple_match.group(0)
                        full_match_str = found_json_str

                    if found_json_str:
                        try:
                            # Пытаемся распарсить найденный кусок
                            extracted_data = json.loads(found_json_str)
                            result_data = extracted_data
                            
                            # Удаляем технический JSON из текста, чтобы показать пользователю только чистый ответ
                            if full_match_str:
                                clean_text = bot_reply.replace(full_match_str, "").strip()
                            
                            result_data["raw_text"] = clean_text
                            return result_data
                            
                        except json.JSONDecodeError:
                            # Если нашли что-то похожее на JSON, но это не валидный JSON
                            pass
                    
                    # Если JSON не нашли — возвращаем просто текст ответа
                    return {"raw_text": clean_text}

        except Exception as e:
            logger.error(f"❌ Exception in parse_intent: {e}")
            return {}
