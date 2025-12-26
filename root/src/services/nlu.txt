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

    async def parse_intent(self, text: str, user_id: int):
        payload = {"bot_id": self.bot_id, "chat_id": str(user_id), "message": text}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.base_url, json=payload, timeout=15.0)
                data = response.json()
                ai_text = data.get("done", "")
                
                # Ищем JSON в ответе (улучшенный поиск последнего JSON-блока)
                matches = list(re.finditer(r'\{.*?\}', ai_text, re.DOTALL))
                if matches:
                    last_match = matches[-1]
                    try:
                        res = json.loads(last_match.group())
                        # Если JSON пустой или неполный, возвращаем только текст
                        if not res.get("origin") or not res.get("destination"):
                            return {"raw_text": ai_text.replace(last_match.group(), "").strip() or ai_text}
                        
                        # Если данные есть, вырезаем JSON из текста и сохраняем его в raw_text
                        res["raw_text"] = ai_text.replace(last_match.group(), "").strip()
                        return res
                    except json.JSONDecodeError:
                        return {"raw_text": ai_text}
                
                # Если JSON нет — возвращаем только текст для общения
                return {"raw_text": ai_text}
                
        except Exception as e:
            logger.error(f"NLU Parsing Error: {e}")
            return None