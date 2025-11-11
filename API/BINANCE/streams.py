# import aiohttp
# import asyncio
# import json
# import traceback
# import contextlib
# from typing import Optional, List
# from datetime import datetime
# from b_context import BotContext
# from c_log import ErrorHandler


# class WS_Prices:
#     """Менеджер WebSocket-соединения для получения рыночных данных (Binance Futures) с поддержкой ротации прокси."""

#     def __init__(
#         self,
#         context: BotContext,
#         info_handler: ErrorHandler,
#         proxy_list: Optional[List[str]] = None,
#         ws_url: str = "wss://fstream.binance.com/"
#     ):
#         info_handler.wrap_foreign_methods(self)
#         self.info_handler = info_handler
#         self.context = context

#         # ======================
#         # Параметры WS
#         # ======================
#         self.ws_task: Optional[asyncio.Task] = None
#         self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None
#         self.session: Optional[aiohttp.ClientSession] = None
#         self.ws_shutdown_event: asyncio.Event = asyncio.Event()
#         self.is_connected: bool = False

#         # ======================
#         # Конфигурация
#         # ======================
#         self.proxy_list = proxy_list or [None]
#         self.proxy_index = 0
#         self.proxy_url = self.proxy_list[self.proxy_index]

#         self.WEBSOCKET_URL: str = ws_url
#         self.max_reconnect_attempts: int = 50
#         self.reconnect_attempts: int = 0

#     # ============================================================
#     #  Обработка сообщений
#     # ============================================================
#     async def handle_ws_message(self, message: str) -> None:
#         try:
#             payload = json.loads(message)
#             data = payload.get("data")
#             if not data:
#                 return

#             stream_type = payload.get("stream", "")
#             symbol = data.get("s")
#             if not symbol:
#                 return

#             if "@markPrice@" in stream_type:
#                 self.context.ws_price_data.setdefault(symbol, {})["fair"] = float(data["p"])
#             elif "@trade" in stream_type:
#                 self.context.ws_price_data.setdefault(symbol, {})["last"] = float(data["p"])

#             item = self.context.ws_price_data.get(symbol)
#             print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol} → "
#                   f"last={item.get('last')} | fair={item.get('fair')}")

#         except Exception as e:
#             self.info_handler.debug_error_notes(f"[WS Handle] Error: {e}\n{traceback.format_exc()}")

#     # ============================================================
#     #  KeepAlive Ping
#     # ============================================================
#     async def keepalive_ping(self) -> None:
#         while not self.ws_shutdown_event.is_set() and self.websocket:
#             try:
#                 await self.websocket.ping()
#                 await asyncio.sleep(15)
#             except Exception as e:
#                 self.info_handler.debug_error_notes(f"[Ping] Ошибка: {e}")
#                 break

#     # ============================================================
#     #  Смена прокси и создание сессии
#     # ============================================================
#     async def _switch_to_next_proxy(self):
#         """Переключает на следующий прокси."""
#         self.proxy_index = (self.proxy_index + 1) % len(self.proxy_list)
#         self.proxy_url = self.proxy_list[self.proxy_index]
#         self.info_handler.debug_info_notes(f"[WS] Переключение на прокси → {self.proxy_url or 'без прокси'}")

#     async def _create_new_session(self):
#         """Создаёт новую сессию с учётом текущего прокси."""
#         if self.session and not self.session.closed:
#             await self.session.close()

#         connector = aiohttp.TCPConnector(ssl=False)
#         if self.proxy_url:
#             self.session = aiohttp.ClientSession(
#                 connector=connector,
#                 trust_env=False,
#                 proxy=self.proxy_url
#             )
#         else:
#             self.session = aiohttp.ClientSession(connector=connector)
#         self.info_handler.debug_info_notes(f"[WS] Создана новая aiohttp-сессия ({self.proxy_url or 'без прокси'})")

#     # ============================================================
#     #  Основной цикл WS
#     # ============================================================
#     async def connect_and_handle(self, symbols: List[str]) -> None:
#         if not symbols:
#             self.info_handler.debug_error_notes("[WS] Пустой список символов")
#             return

#         # Формируем стримы
#         streams = []
#         for s in symbols:
#             s_lower = s.lower()
#             streams.append(f"{s_lower}@trade")
#             streams.append(f"{s_lower}@markPrice@1s")
#         ws_url = f"{self.WEBSOCKET_URL}stream?streams={'/'.join(streams)}"

#         while self.reconnect_attempts < self.max_reconnect_attempts and not self.ws_shutdown_event.is_set():
#             try:
#                 await self._create_new_session()

#                 self.websocket = await self.session.ws_connect(
#                     ws_url,
#                     autoping=False,
#                 )

#                 self.is_connected = True
#                 self.reconnect_attempts = 0
#                 self.info_handler.debug_info_notes(f"[WS] Подключено успешно через {self.proxy_url or 'без прокси'}")

#                 ping_task = asyncio.create_task(self.keepalive_ping())

#                 async for msg in self.websocket:
#                     if self.ws_shutdown_event.is_set():
#                         await self.websocket.close(code=1000, message=b"Shutdown")
#                         break

#                     if msg.type == aiohttp.WSMsgType.TEXT:
#                         await self.handle_ws_message(msg.data)
#                     elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
#                         raise ConnectionError(f"WS closed/error: {msg.type}")

#                 ping_task.cancel()
#                 with contextlib.suppress(asyncio.CancelledError):
#                     await ping_task

#             except Exception as e:
#                 self.info_handler.debug_error_notes(f"[WS Error] {e}\n{traceback.format_exc()}")
#                 self.reconnect_attempts += 1
#                 await self._switch_to_next_proxy()
#                 backoff = min(2 * self.reconnect_attempts, 10)
#                 await asyncio.sleep(backoff)
#                 continue

#         self.is_connected = False
#         self.info_handler.debug_error_notes("[WS] Достигнут лимит переподключений, поток остановлен")

#     # ============================================================
#     #  Управление
#     # ============================================================
#     async def connect_to_websocket(self, symbols: List[str]) -> None:
#         try:
#             await self.stop_ws_process()
#             self.ws_shutdown_event.clear()
#             self.reconnect_attempts = 0
#             self.ws_task = asyncio.create_task(self.connect_and_handle(symbols))
#         except Exception as e:
#             self.info_handler.debug_error_notes(f"[WS Connect] Failed: {e}")

#     async def restart_ws(self):
#         try:
#             await self.stop_ws_process()
#             await self.connect_to_websocket(list(self.context.fetch_symbols))
#             self.info_handler.debug_info_notes("[WS] Перезапущен")
#         except Exception as e:
#             self.info_handler.debug_error_notes(f"[WS Restart] Ошибка: {e}")

#     async def stop_ws_process(self) -> None:
#         self.ws_shutdown_event.set()

#         if self.ws_task:
#             self.ws_task.cancel()
#             with contextlib.suppress(asyncio.CancelledError):
#                 await asyncio.wait_for(self.ws_task, timeout=5)
#             self.ws_task = None
#             self.is_connected = False

#         if self.websocket:
#             await self.websocket.close()
#             self.websocket = None

#         if self.session and not self.session.closed:
#             await self.session.close()

#         self.info_handler.debug_info_notes("[WS] Процесс остановлен")

#     async def sync_ws_streams(self, active_symbols: list) -> None:
#         """Точка входа, как и раньше."""
#         new_set = set(active_symbols)
#         if new_set != getattr(self, "last_symbols_set", set()):
#             self.last_symbols_set = new_set
#             if new_set:
#                 await self.connect_to_websocket(list(new_set))
#             else:
#                 await self.stop_ws_process()
