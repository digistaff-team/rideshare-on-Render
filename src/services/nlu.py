import aiohttp
import logging
import json
import os
import re

logger = logging.getLogger(__name__)

class NLUProcessor:
    def __init__(self):
        # Используем переменные окружения PROTALK_*
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
                        bot_reply = api_response.get("done", "")
                    except json.JSONDecodeError:
                        logger.error("❌ Failed to decode API response")
                        return {}

                    # --- 2. Логика поиска и удаления JSON ---
                    
                    # Ищем JSON-объект {...}
                    # Мы ищем все совпадения, чтобы найти последний (обычно самый полный)
                    # Используем re.DOTALL, чтобы захватить переносы строк внутри JSON
                    json_matches = list(re.finditer(r"\{.*\}", bot_reply, re.DOTALL))
                    
                    result_data = {}
                    clean_text = bot_reply
                    
                    if json_matches:
                        # Берем последний найденный блок
                        last_match = json_matches[-1]
                        json_str = last_match.group(0)
                        
                        try:
                            result_data = json.loads(json_str)
                            
                            # Если парсинг прошел успешно, ВЫРЕЗАЕМ этот кусок из текста
                            # replace(..., 1) удаляет только одно вхождение (на всякий случай)
                            # но лучше использовать строгую замену по позиции, если возможно,
                            # но replace здесь сработает отлично, т.к. текст точный.
                            clean_text = bot_reply.replace(json_str, "").strip()
                            
                        except json.JSONDecodeError:
                            pass
                    
                    # --- 3. Финальная зачистка ---
                    # Удаляем остатки Markdown-оберток (```json, ```, и т.д.), если они были ВОКРУГ удаленного JSON
                    clean_text = re.sub(r"```.*?```", "", clean_text, flags=re.DOTALL).strip()
                    clean_text = clean_text.replace("```", "").strip()
                    clean_text = re.sub(r"^\s*json\s*", "", clean_text, flags=re.MULTILINE).strip()
                    
                    # Возвращаем результат
                    if result_data:
                        result_data["raw_text"] = clean_text
                        return result_data
                    
                    return {"raw_text": clean_text}

        except Exception as e:
            logger.error(f"❌ Exception in parse_intent: {e}")
            return {}
