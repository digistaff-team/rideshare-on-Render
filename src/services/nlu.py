import aiohttp
import logging
import json
import os
import re

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

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    resp_text = await resp.text()
                    
                    if resp.status != 200:
                        logger.error(f"❌ API Error {resp.status}")
                        return {}

                    try:
                        api_response = json.loads(resp_text)
                        bot_reply = api_response.get("done", "")
                    except json.JSONDecodeError:
                        return {}

                    # 1. Сначала ищем JSON-блок в Markdown (``````)
                    markdown_json_match = re.search(r'``````', bot_reply, re.DOTALL)
                    
                    # 2. Или просто JSON-объект {...}
                    simple_json_match = re.search(r'\{.*\}', bot_reply, re.DOTALL)

                    result_data = {}
                    clean_text = bot_reply

                    # Определяем, что мы нашли
                    found_json_str = None
                    full_match_str = None # Что нужно вырезать из текста

                    if markdown_json_match:
                        found_json_str = markdown_json_match.group(1) # Только содержимое {}
                        full_match_str = markdown_json_match.group(0) # Весь блок ``````
                    elif simple_json_match:
                        found_json_str = simple_json_match.group(0)
                        full_match_str = found_json_str

                    if found_json_str:
                        try:
                            extracted_data = json.loads(found_json_str)
                            result_data = extracted_data
                            
                            # Вырезаем найденный блок из текста
                            if full_match_str:
                                clean_text = bot_reply.replace(full_match_str, "").strip()
                            
                            result_data["raw_text"] = clean_text
                            return result_data
                            
                        except json.JSONDecodeError:
                            pass
                    
                    # Если JSON не нашли или он битый
                    return {"raw_text": clean_text}

        except Exception as e:
            logger.error(f"❌ Exception: {e}")
            return {}
