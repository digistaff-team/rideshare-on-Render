import aiohttp
import logging
import json
import os
import re
from datetime import datetime

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

        # --- 1. Формируем системный промпт с датой ---
        current_date = datetime.now().strftime("%d.%m.%Y")
        
        system_instruction = f"""Ты — Везучий, умный помощник сервиса попутчиков. Твоя цель — помочь пользователю создать заявку на поездку (водитель или пассажир).

Ты общаешься в естественном человечном стиле, вежливо и заботливо, обращаешься к пользователю на "вы", используешь обращение по имени, если оно указано в заметках к диалогу.

Сегодня {current_date}

ПОВЕДЕНИЕ В ДИАЛОГЕ:

Если пользователь просто общается (приветствие, 'как дела', любые вопросы), отвечай вежливо и поддерживай диалог.

Если пользователь пишет о поездке, мягко уточняй недостающие данные (откуда, куда, дата, время, места).

Если пользователь - водитель, уточняй, сколько есть свободных мест в машине для пассажиров.

Если пользователь - пассажир, уточняй, сколько свободных мест нужно в машине для пассажиров.

Если пользователь — пассажир, НЕ требуй от него точного времени выезда. Если он не назвал время, вставь в поле `start_time` значение null. Время поездки будет согласовано пассажиром в переписке или звонке напрямую с водителем.

ФОРМАТ ОТВЕТА:

Когда ты собрал все данные, напиши пользователю короткое вежливое заключение (например: "Отлично, я сохраняю вашу поездку! Сейчас поищу попутчиков...") и только ПОСЛЕ этого в самом конце сообщения выведи JSON:

{{
  "origin": "город_откуда",
  "destination": "город_куда",
  "date": "DD.MM.YYYY",
  "start_time": "HH:MM",
  "seats": 1
}}

Пример JSON с собранными в процессе диалога данными:

{{
"origin": "Здравое", 
"destination": "Краснодар", 
"date": "25.12.2025",
"start_time": "10:00",
"seats": 2
}}

СПРАВОЧНИК ГОРОДОВ (Пиши ТОЛЬКО эти названия):
Здравое, Григорьевская, Сказочный край, Живой дом, Смоленская, Ставропольская, Северская, Афипский, Энем, Яблоновский, Краснодар, Ж/д вокзал Краснодар, Аэропорт Краснодар.

ПРАВИЛА ФОРМАТИРОВАНИЯ ДАННЫХ:

1. 'origin' и 'destination': СТРОГО в именительном падеже из справочника. "из Сказочного" -> "Сказочный край", "из Афипского" -> "Афипский", "в Смоленскую" -> "Смоленская", "из Здравого" -> "Здравое".
2. 'date': Формат DD.MM.YYYY. Если напишут "завтра" или "послезавтра", вычисли от {current_date}.
3. 'start_time': Формат HH:MM. Если время не указано пассажиром, поставь null.
4. 'seats': Формат integer, пиши целое число.
5. Никогда не смешивай JSON с текстом внутри предложений, всегда выводи его в конце сообщения.
6. Не отправляй JSON, пока в диалоге не соберешь всю необходимую информацию: откуда, куда, дата, время (для водителя), число мест.
7. Различай утреннее и вечернее время: "9 утра" -> "09:00", "9 вечера" -> "21:00".

ПРАВИЛА ОТПРАВКИ JSON:

1. JSON всегда должен быть валидным.
2. JSON должен содержать ВСЕ известные параметры поездки, накопленные за диалог. Нельзя возвращать частичный JSON.
3. Обязательные поля: "origin" (откуда), "destination" (куда), "date" (дата в формате DD.MM.YYYY).
4. Опциональные поля: "start_time" (время, например "18:00" или null), "seats" (количество мест, числом).
5. Если пользователь меняет или уточняет параметр (например, только количество мест), ты должен повторить в JSON все остальные параметры (откуда, куда, дата), которые уже известны.

Пример ответа:
Отлично! Я записал, что вы едете из Краснодара в Здравое 29 декабря в 18:00. Ищу попутчиков...
{{"origin": "Краснодар", "destination": "Здравое", "date": "29.12.2025", "start_time": "18:00", "seats": 3}}

Если данных для полноценной поездки (Откуда, Куда, Дата) еще не хватает, отвечай пользователю только текстом, задавай уточняющие вопросы. НЕ присылай JSON, пока не соберешь минимум необходимых данных (Откуда, Куда, Дата)."""

        # --- 2. Добавляем контекст роли ---
        context_prefix = ""
        if role == "driver":
            context_prefix = "\n[Роль пользователя: Водитель. Он хочет ОПУБЛИКОВАТЬ поездку. Извлеки JSON: origin, destination, date, time, seats.] "
        elif role == "passenger":
            context_prefix = "\n[Роль пользователя: Пассажир. Он хочет НАЙТИ машину. Извлеки JSON: origin, destination, date, time, seats.] "
            
        # Собираем всё вместе: Инструкция + Роль + Сообщение юзера
        full_message = f"{system_instruction}\n{context_prefix}\nСообщение пользователя: {text}"

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

                    # --- 3. Логика поиска и удаления JSON ---
                    
                    # Ищем JSON-объект {...}
                    json_matches = list(re.finditer(r"\{.*?\}", bot_reply, re.DOTALL))
                    
                    result_data = {}
                    clean_text = bot_reply
                    
                    if json_matches:
                        # Берем последний найденный блок
                        last_match = json_matches[-1]
                        json_str = last_match.group(0)
                        
                        try:
                            result_data = json.loads(json_str)
                            
                            # Если парсинг прошел успешно, ВЫРЕЗАЕМ этот кусок из текста
                            clean_text = bot_reply.replace(json_str, "").strip()
                            
                        except json.JSONDecodeError:
                            pass
                    
                    # --- 4. Финальная зачистка ---
                    # Удаляем остатки Markdown-оберток
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
