# API.TG.tg_notifier.py

import asyncio
import aiohttp
import random
from typing import *
from a_config import DIFF_PCT
from c_log import ErrorHandler, log_time
from c_utils import to_human_digit


class TelegramNotifier():
    def __init__(
            self,
            token: str,
            chat_ids: list[int],
            info_handler: ErrorHandler,
            stop_bot: bool,
        ):
        self.token = token
        self.chat_ids = [x.strip() for x in chat_ids if x and isinstance(x, str)]
        self.base_tg_url = f"https://api.telegram.org/bot{self.token}"
        self.send_text_endpoint = "/sendMessage"
        self.send_photo_endpoint = "/sendPhoto"
        self.delete_msg_endpoint = "/deleteMessage"

        info_handler.wrap_foreign_methods(self)
        self.info_handler = info_handler
        self.stop_bot = stop_bot

    async def send(
        self,
        text: str,
        photo_bytes: bytes = None,
        disable_notification: bool = False,
        max_retries: int = float("inf"),
    ):
        """
        Отправка сообщения с авто-реконнектом и повторными попытками.
        """

        async def _try_send(session: aiohttp.ClientSession, chat_id):
            if photo_bytes:
                url = self.base_tg_url + self.send_photo_endpoint
                data = aiohttp.FormData()
                data.add_field("chat_id", str(chat_id))
                data.add_field("caption", text or "")
                data.add_field("parse_mode", "HTML")
                data.add_field("disable_web_page_preview", "true")
                data.add_field("disable_notification", str(disable_notification).lower())
                data.add_field("photo", photo_bytes, filename="spread.png", content_type="image/png")
            else:
                url = self.base_tg_url + self.send_text_endpoint
                data = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                    "disable_notification": disable_notification,
                }

            # Повторные попытки с backoff
            attempt = 0
            while not self.stop_bot:
                attempt += 1
                try:
                    async with session.post(url, data=data, timeout=10) as resp:
                        if resp.status != 200:
                            err_text = await resp.text()
                            raise Exception(f"HTTP {resp.status}: {err_text}")

                        # response_json = await resp.json()
                        # message_id = response_json.get("result", {}).get("message_id")
                        return True  # успех

                except Exception as e:
                    wait_time = random.uniform(1, 3)  # backoff
                    if self.info_handler:
                        self.info_handler.debug_error_notes(
                            f"[TelegramSender] Попытка {attempt}/{max_retries} не удалась ({e}), "
                            f"повтор через {wait_time:.1f}с",
                            is_print=True,
                        )
                    if attempt == max_retries:
                        return False
                    await asyncio.sleep(wait_time)

        # Новый session для каждой пачки отправок
        async with aiohttp.ClientSession() as session:
            tasks = [_try_send(session, chat_id) for chat_id in self.chat_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return all(r is True for r in results)     


class Formatter:
    """
    Форматирует сообщения для Telegram с лёгкой визуальной кодировкой:
    🟢 — fair > last  → потенциал роста
    🔴 — fair < last  → перегрев
    ⚪ — нейтрально (разница меньше порога)
    """

    @staticmethod
    def format_coins_for_tg(
        signal_data: Dict,
        title: str = f"Fair > Last и Δ ≥ {DIFF_PCT}%",
    ) -> str:
        """
        Форматирует список монет для Telegram.

        coins: [
            {"symbol": str, "last_price": float, "fair_price": float,
             "diff_percent": float, "price_precision": int},
            ...
        ]
        """

        prec = signal_data.get("price_precision", 2)
        last_price = to_human_digit(round(signal_data["last_price"], prec))
        fair_price = to_human_digit(round(signal_data["fair_price"], prec))
        diff = signal_data["diff_percent"]

        if diff >= DIFF_PCT:
            icon = "🟢"
        elif diff <= -DIFF_PCT:
            icon = "🔴"
        else:
            icon = "⚪"

        return (
            f"📊 {title}\n\n"
            f"{icon} {signal_data['symbol']:10}\n"
            f"last: {last_price:<10} fair: {fair_price:<10}\n"
            f"Δ: {diff:+.2f}%"
        )