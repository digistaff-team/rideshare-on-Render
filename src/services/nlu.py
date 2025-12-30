import aiohttp
import logging
import json
import os
import re  # 👈 Добавляем модуль регулярных выражений

logger = logging.getLogger(__name__)

class NLUProcessor:
    def __init__(self):
        self.api_token = os.getenv("PRO_TALK_TOKEN") 
        self.bot_id = os.getenv("PRO_TALK_BOT_ID")
        self.base_url = "https://api.pro-talk.ru/api/v1.0/ask"

    async def parse_intent(self, text: str, user_id: int) -> dict:
        if not self.api_token or not self.bot_id:
             logger.error("❌ Tokens missing")
             return {}

        url = f"{self.base_url}/{self.api_token}"
        payload = {
            "bot_id": int(self.bot_id),
            "chat_id": str(user_id),
            "message": text
        }

        print(f"📡 NLU REQUEST: {text}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    resp_text = await resp.text()
                    
                    if resp.status != 200:
                        logger.error(f"❌ API Error {resp.status}: {resp_text}")
                        return {}

                    # Парсим ответ от самого API (там есть поле "done")
                    try:
                        api_response = json.loads(resp_text)
                        bot_reply = api_response.get("done", "")
                    except json.JSONDecodeError:
                        logger.error("❌ Invalid API response format")
                        return {}
                    
                    print(f"📥 BOT REPLY: {bot_reply}")

                    # --- САМОЕ ГЛАВНОЕ: Ищем JSON внутри текста ответа ---
                    # Ищем всё, что похоже на JSON-объект {...}
                    # Флаг DOTALL позволяет захватывать переносы строк
                    json_match = re.search(r'\{.*\}', bot_reply, re.DOTALL)
                    
                    result_data = {}

                    if json_match:
                        json_str = json_match.group(0)
                        try:
                            # Пытаемся распарсить найденный кусок
                            extracted_data = json.loads(json_str)
                            
                            # Если успешно - это наши данные
                            result_data = extracted_data
                            
                            # Убираем JSON из текста, чтобы показать пользователю чистый ответ
                            clean_text = bot_reply.replace(json_str, "").strip()
                            result_data["raw_text"] = clean_text
                            
                            print(f"✅ EXTRACTED DATA: {result_data}")
                            return result_data
                            
                        except json.JSONDecodeError:
                            print("⚠️ JSON found but invalid")
                            pass
                    
                    # Если JSON не найден или не валиден - возвращаем просто текст
                    # Это значит, что бот еще уточняет детали
                    return {"raw_text": bot_reply}

        except Exception as e:
            logger.error(f"❌ Exception: {e}")
            return {}
