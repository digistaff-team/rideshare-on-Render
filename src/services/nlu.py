import os
import json
import httpx
import logging
import re

logger = logging.getLogger(__name__)

class NLUProcessor:
    def __init__(self):
        self.api_token = os.getenv("PROTALK_TOKEN")
        self.bot_id = int(os.getenv("PROTALK_BOT_ID", 0))
        self.base_url = f"https://api.pro-talk.ru/api/v1.0/ask/{self.api_token}"

    async def parse_intent(self, text: str, user_id: int, role: str = None):
        """
        Отправляет запрос в Pro-Talk с указанием роли пользователя.
        """
        # Формируем контекст для LLM
        context_prefix = ""
        if role == "driver":
            context_prefix = "[Роль: Водитель. Предлагаю поездку] "
        elif role == "passenger":
            context_prefix = "[Роль: Пассажир. Ищу поездку] "
            
        full_message = f"{context_prefix}{text}"

        payload = {
            "bot_id": self.bot_id, 
            "chat_id": str(user_id), 
            "message": full_message
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.base_url, json=payload, timeout=25.0)
                data = response.json()
                ai_text = data.get("done", "")
                
                # Ищем JSON в ответе
                matches = list(re.finditer(r'\{.*?\}', ai_text, re.DOTALL))
                if matches:
                    last_match = matches[-1]
                    try:
                        res = json.loads(last_match.group())
                        
                        # Если не хватает данных, возвращаем только текст
                        if not res.get("origin") or not res.get("destination") or not res.get("date"):
                             return {"raw_text": ai_text}

                        res["raw_text"] = ai_text.replace(last_match.group(), "").strip()
                        return res
                    except json.JSONDecodeError:
                        return {"raw_text": ai_text}
                
                return {"raw_text": ai_text}
                
        except Exception as e:
            logger.error(f"NLU Parsing Error: {e}")
            return None
