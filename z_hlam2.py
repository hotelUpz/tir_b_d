    
    # async def get_klines(
    #         self,
    #         session: aiohttp.ClientSession,
    #         symbol: str,
    #         interval: str,
    #         limit: int,
    #         api_key: str = None
    #     ):
    #     """
    #     Загружает до 2500 и более минутных свечей, если limit > 1000 — разбивает на части с использованием endTime.
    #     """
    #     MAX_LIMIT = 1000
    #     all_data = []

    #     headers = {"X-MBX-APIKEY": api_key} if api_key else {}
    #     end_time = int(time.time() * 1000)  # текущее время в мс
    #     remaining = limit

    #     if limit <= 0:
    #         self.error_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name}")
    #         return pd.DataFrame(columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
        
    #     base_sleep = 0.1  
    #     try:
    #         while remaining > 0:
    #             fetch_limit = min(MAX_LIMIT, remaining)
    #             params = {
    #                 "symbol": symbol,
    #                 "interval": interval,
    #                 "limit": fetch_limit,
    #                 "endTime": end_time
    #             }

    #             async with session.get(self.klines_url, params=params, headers=headers, proxy=self.proxy_url) as response:
    #                 if response.status != 200:
    #                     self.error_handler.debug_error_notes(f"Failed to fetch klines: {response.status}, symbol: {symbol}, {await response.text()}")
    #                     break

    #                 klines = await response.json()
    #                 if not klines:
    #                     break

    #                 all_data = klines + all_data  # prepend to preserve chronological order
    #                 end_time = klines[0][0] - 1  # сдвигаем назад на 1мс до первой свечи
    #                 remaining -= len(klines)

    #             await asyncio.sleep(base_sleep)  # предотвратить бан

    #         if not all_data:
    #             return pd.DataFrame(columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])

    #         df = pd.DataFrame(all_data).iloc[:, :6]
    #         df.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
    #         df['Time'] = pd.to_datetime(df['Time'], unit='ms')
    #         df.set_index('Time', inplace=True)
    #         df = df.astype(float).sort_index()
    #         df['Volume'] = df['Volume'].abs()  # делаем объём положительным

    #         return df.tail(limit)  # возвращаем ровно limit последних свечей

    #     except Exception as ex:
    #         self.error_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name}")
    #         return pd.DataFrame(columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])


    
    # @staticmethod
    # def get_qty_precisions(symbol_info, symbol):
    #     symbol_data = next((item for item in symbol_info["symbols"] if item['symbol'] == symbol), None)
    #     if not symbol_data:
    #         return

    #     lot_size_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "LOT_SIZE"), None)
    #     price_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "PRICE_FILTER"), None)

    #     if not lot_size_filter or not price_filter:
    #         return

    #     def count_decimal_places(number_str):
    #         if '.' in number_str:
    #             return len(number_str.rstrip('0').split('.')[-1])
    #         return 0

    #     qty_precission = count_decimal_places(lot_size_filter['stepSize'])
    #     price_precision = count_decimal_places(price_filter['tickSize'])

    #     return qty_precission, price_precision



        # self.proxy_url = None
        # if proxy_cfg.get("enable"):
        #     try:
        #         login = proxy_cfg.get("proxy_login")
        #         password = proxy_cfg.get("proxy_password")
        #         host = proxy_cfg.get("proxy_address")
        #         port = proxy_cfg.get("proxy_port")
        #         self.proxy_url = f"http://{login}:{password}@{host}:{port}"
        #     except Exception as ex:
        #         print(ex)


# price_precision = precisions[1] if precisions else 2




                # # Форматируем и отправляем сообщение через Formatter + TelegramNotifier
                # if coins_to_report:
                #     report_text = Formatter.format_coins_for_tg(coins_to_report)
                #     print(report_text)
                #     self.notifier.report_list.append(report_text)
                #     await self.notifier.send_report_batches(batch_size=1)
# precisions = self.binance_public.get_precisions(symbol)


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
#     """Менеджер WebSocket-соединения для получения рыночных данных (Binance Futures)."""

#     def __init__(self, context: BotContext, error_handler: ErrorHandler, proxy_url: Optional[str] = None,
#                  ws_url: str = "wss://fstream.binance.com/"):
#         error_handler.wrap_foreign_methods(self)
#         self.error_handler = error_handler
#         self.context = context

#         self.session: Optional[aiohttp.ClientSession] = None
#         self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None

#         self.ws_task: Optional[asyncio.Task] = None
#         self.is_connected: bool = False
#         self.max_reconnect_attempts: int = 50
#         self.reconnect_attempts: int = 0
#         self.ws_shutdown_event: asyncio.Event = asyncio.Event()
#         self.WEBSOCKET_URL: str = ws_url
#         self.last_symbol_progress = 0

#         self.proxy_url: Optional[str] = proxy_url
#         self.proxy_auth: Optional[aiohttp.BasicAuth] = None

#     # ============================================================
#     #  Основная обработка входящих сообщений
#     # ============================================================
#     async def handle_ws_message(self, message: str) -> None:
#         try:
#             payload = json.loads(message)
#             data = payload.get("data")
#             if not data:
#                 return

#             stream_type = payload.get("stream", "")
#             if "@markPrice@" in stream_type:  # справедливая (mark/fair)
#                 symbol = data["s"]
#                 mark_price = float(data["p"])
#                 item = self.context.ws_price_data.setdefault(symbol, {})
#                 item["fair"] = mark_price

#             elif "@trade" in stream_type:  # последняя цена (last)
#                 symbol = data["s"]
#                 last_price = float(data["p"])
#                 item = self.context.ws_price_data.setdefault(symbol, {})
#                 item["last"] = last_price

#             # Отображаем в консоль для наглядности
#             item = self.context.ws_price_data.get(symbol)
#             print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol} → "
#                   f"last={item.get('last')} | fair={item.get('fair')}")

#         except Exception as e:
#             self.error_handler.debug_error_notes(
#                 f"[WS Handle] Error: {e}\n{traceback.format_exc()}"
#             )

#     # ============================================================
#     #  Пинг KeepAlive
#     # ============================================================
#     async def keepalive_ping(self) -> None:
#         while not self.ws_shutdown_event.is_set() and self.websocket:
#             try:
#                 await self.websocket.ping()
#                 await asyncio.sleep(15)
#             except Exception as e:
#                 self.error_handler.debug_error_notes(f"[Ping] Ошибка: {e}")
#                 break

#     # ============================================================
#     #  Подключение и цикл чтения
#     # ============================================================
#     async def connect_and_handle(self, symbols: List[str]) -> None:
#         if not symbols:
#             self.error_handler.debug_error_notes("Empty symbols list provided")
#             return

#         # Подписываемся сразу на last (trade) и fair (markPrice)
#         streams = []
#         for s in symbols:
#             s_lower = s.lower()
#             streams.append(f"{s_lower}@trade")        # последняя цена
#             streams.append(f"{s_lower}@markPrice@1s") # справедливая цена

#         ws_url = f"{self.WEBSOCKET_URL}stream?streams={'/'.join(streams)}"

#         if not self.session:
#             self.session = aiohttp.ClientSession()

#         while self.reconnect_attempts < self.max_reconnect_attempts:
#             if self.ws_shutdown_event.is_set():
#                 break
#             try:
#                 self.websocket = await self.session.ws_connect(
#                     ws_url,
#                     proxy=self.proxy_url,
#                     proxy_auth=self.proxy_auth,
#                     autoping=False,
#                 )

#                 self.is_connected = True
#                 self.reconnect_attempts = 0
#                 ping_task = asyncio.create_task(self.keepalive_ping())

#                 async for msg in self.websocket:
#                     if self.ws_shutdown_event.is_set():
#                         await self.websocket.close(code=1000, message=b"Shutdown")
#                         break

#                     if msg.type == aiohttp.WSMsgType.TEXT:
#                         await self.handle_ws_message(msg.data)
#                     elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
#                         break

#                 ping_task.cancel()
#                 with contextlib.suppress(asyncio.CancelledError):
#                     await ping_task

#             except Exception as e:
#                 self.error_handler.debug_error_notes(
#                     f"[WS Error] {e}\n{traceback.format_exc()}"
#                 )

#             self.reconnect_attempts += 1
#             backoff = min(2 * self.reconnect_attempts, 10)
#             await asyncio.sleep(backoff)

#         self.is_connected = False
#         self.error_handler.debug_error_notes("Max reconnect attempts reached, WebSocket stopped")

#     # ============================================================
#     #  Управление (публичные методы)
#     # ============================================================
#     async def connect_to_websocket(self, symbols: List[str]) -> None:
#         try:
#             await self.stop_ws_process()
#             self.ws_shutdown_event.clear()
#             self.reconnect_attempts = 0
#             self.ws_task = asyncio.create_task(self.connect_and_handle(symbols))
#         except Exception as e:
#             self.error_handler.debug_error_notes(f"[WS Connect] Failed: {e}")

#     async def restart_ws(self):
#         try:
#             await self.stop_ws_process()
#             await self.connect_to_websocket(list(self.context.fetch_symbols))
#             self.error_handler.debug_info_notes("[WS] Вебсокет перезапущен")
#         except Exception as e:
#             self.error_handler.debug_error_notes(f"[WS Restart] Ошибка: {e}")

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

#         self.error_handler.debug_info_notes("WebSocket process stopped")

#     async def sync_ws_streams(self, active_symbols: list) -> None:
#         """Точка входа, как и раньше."""
#         new_set = set(active_symbols)
#         if new_set != getattr(self, "last_symbols_set", set()):
#             self.last_symbols_set = new_set
#             if new_set:
#                 await self.connect_to_websocket(list(new_set))
#             else:
#                 await self.stop_ws_process()



# class TrendConfirmSignal:
#     """
#     Проверяет направление тренда по короткой и длинной EMA.
#     Восходящий тренд, если EMA(fast) > EMA(slow).
#     Если индикатор отключён — тренд считается восходящим ("UP").
#     """

#     def __init__(self):
#         self.trend_cfg = TREND_LINE

#         # Берём первый ключ из конфигурации (например, "5m")
#         self.tf = next(iter(self.trend_cfg.keys()), "5m")

#         cfg = self.trend_cfg.get(self.tf, {})
#         self.enabled = cfg.get("enable", False)
#         self.fast = cfg.get("fast", 5)
#         self.slow = cfg.get("slow", 10)

#     @staticmethod
#     def _ema(values: List[float], period: int) -> float:
#         """Быстрое вычисление EMA по последним period значениям."""
#         if len(values) < period:
#             return float("nan")
#         weights = np.exp(np.linspace(-1., 0., period))
#         weights /= weights.sum()
#         return float(np.convolve(values, weights, mode="valid")[-1])

#     def detect_trend(self, closes: List[float]) -> Optional[str]:
#         """
#         Принимает массив закрытий (closes).
#         Возвращает 'UP' | 'DOWN' | None (если данных недостаточно).
#         """
#         # если индикатор отключён — считаем тренд восходящим
#         if not self.enabled:
#             return "UP"

#         if len(closes) < self.slow:
#             return None  # данных мало — нельзя определить тренд

#         fast_ema = self._ema(closes[-self.fast:], self.fast)
#         slow_ema = self._ema(closes[-self.slow:], self.slow)

#         if np.isnan(fast_ema) or np.isnan(slow_ema):
#             return None

#         if fast_ema > slow_ema:
#             return "UP"
#         elif fast_ema < slow_ema:
#             return "DOWN"
#         return None





        
        # size = size_calc(
        #     margin_size: float,
        #     entry_price: float,
        #     leverage: float,
        #     volume_rate: float,
        #     precision: int,
        #     dubug_label: str`
        # )


        # if not ok:
        #     raise RuntimeError("Failed to initialize session for 'public'")

# in_position = False

# if in_position is False:
#     print("mdjjjjjjjjjjjjjj")


# a = {
#     1: 5
# }

# del a[1]

# print(a)






    # async def send_report_batches(self, is_send: bool = True, batch_size: int = 1):
    #     """Отправляет накопленные сообщения в TG пачками по batch_size, удаляя их только после отправки."""
    #     if not isinstance(batch_size, int) or batch_size < 1:
    #         print(f"[ERROR] Invalid batch_size={batch_size!r}: must be int >= 1")
    #         return

    #     while self.report_list:
    #         # Чистим список от пустых значений, не меняя ссылку
    #         self.report_list[:] = [
    #             x for x in self.report_list
    #             if isinstance(x, str) and x.strip()
    #         ]

    #         if not self.report_list:
    #             break

    #         batch = self.report_list[:batch_size]
    #         text_block = "\n\n".join(batch)

    #         try:
    #             if is_send:
    #                 await self.send(
    #                     text=text_block,
    #                     photo_bytes=None,
    #                     disable_notification=False
    #                 )
    #         except Exception as e:
    #             print(f"[ERROR][TG send]: {e} ({log_time()})")

    #         # Удаляем только отправленные сообщения
    #         del self.report_list[:len(batch)]
    #         await asyncio.sleep(0.25)


   


# class Formatter:
#     @staticmethod
#     def format_coins_for_tg(coins: List[Dict], title: str = f"fair > last и diff >= {DIFF_PCT}%") -> str:
#         """
#         Форматирует список монет для Telegram.
#         coins: [{"symbol": str, "last_price": float, "fair_price": float, "diff_percent": float, "price_precision": int}, ...]
#         """
#         if not coins:
#             return "❌ Нет монет с fair > last и отклонением >= 5%"

#         # lines = [f"💹 {title} ({len(coins)} шт):\n"]
#         lines = [f"💹 {title}:\n"]
#         for c in coins:
#             prec = c.get('price_precision', 2)  # default to 2 if not available
#             last_price = to_human_digit(round(c['last_price'], prec))
#             fair_price = to_human_digit(round(c['fair_price'], prec))

#             lines.append(
#                 f"• {c['symbol']}: last={last_price}, fair={fair_price}, "
#                 f"diff={c['diff_percent']:.2f}%"
#             )
#         return "\n".join(lines)



# {'symbol': 'CELOUSDT', 'pair': 'CELOUSDT', 'contractType': 'PERPETUAL', 'deliveryDate': 4133404800000, 'onboardDate': 1632639600000, 'status': 'TRADING', 'maintMarginPercent': '2.5000', 'requiredMarginPercent': '5.0000', 'baseAsset': 'CELO', 'quoteAsset': 'USDT', 'marginAsset': 'USDT', 'pricePrecision': 3, 'quantityPrecision': 1, 'baseAssetPrecision': 8, 'quotePrecision': 8, 'underlyingType': 'COIN', 'underlyingSubType': ['Layer-1'], 'triggerProtect': '0.0500', 'liquidationFee': '0.015000', 'marketTakeBound': '0.05', 'maxMoveOrderLimit': 10000, 'filters': [{'filterType': 'PRICE_FILTER', 'minPrice': '0.010', 'tickSize': '0.001', 'maxPrice': '100000'}, {'maxQty': '5000000', 'minQty': '0.1', 'stepSize': '0.1', 'filterType': 'LOT_SIZE'}, {'maxQty': '500000', 'minQty': '0.1', 'stepSize': '0.1', 'filterType': 'MARKET_LOT_SIZE'}, {'limit': 200, 'filterType': 'MAX_NUM_ORDERS'}, {'filterType': 'MAX_NUM_ALGO_ORDERS', 'limit': 10}, {'filterType': 'MIN_NOTIONAL', 'notional': '5'}, {'multiplierDown': '0.9500', 'multiplierDecimal': '4', 'multiplierUp': '1.0500', 'filterType': 'PERCENT_PRICE'}, {'filterType': 'POSITION_RISK_CONTROL', 'positionControlSide': 'NONE'}], 'orderTypes': ['LIMIT', 'MARKET', 'STOP', 'STOP_MARKET', 'TAKE_PROFIT', 'TAKE_PROFIT_MARKET', 'TRAILING_STOP_MARKET'], 'timeInForce': ['GTC', 'IOC', 'FOK', 'GTX', 'GTD'], 'permissionSets': ['GRID', 'COPY', 'DCA']}


# {'symbol': 'CELOUSDT', 'pair': 'CELOUSDT', 'contractType': 'PERPETUAL', 'deliveryDate': 4133404800000, 'onboardDate': 1632639600000, 'status': 'TRADING', 'maintMarginPercent': '2.5000', 'requiredMarginPercent': '5.0000', 'baseAsset': 'CELO', 'quoteAsset': 'USDT', 'marginAsset': 'USDT', 'pricePrecision': 3, 'quantityPrecision': 1, 'baseAssetPrecision': 8, 'quotePrecision': 8, 'underlyingType': 'COIN', 'underlyingSubType': ['Layer-1'], 'triggerProtect': '0.0500', 'liquidationFee': '0.015000', 'marketTakeBound': '0.05', 'maxMoveOrderLimit': 10000, 'filters': [{'filterType': 'PRICE_FILTER', 'minPrice': '0.010', 'tickSize': '0.001', 'maxPrice': '100000'}, {'maxQty': '5000000', 'minQty': '0.1', 'stepSize': '0.1', 'filterType': 'LOT_SIZE'}, {'maxQty': '500000', 'minQty': '0.1', 'stepSize': '0.1', 'filterType': 'MARKET_LOT_SIZE'}, {'limit': 200, 'filterType': 'MAX_NUM_ORDERS'}, {'filterType': 'MAX_NUM_ALGO_ORDERS', 'limit': 10}, {'filterType': 'MIN_NOTIONAL', 'notional': '5'}, {'multiplierDown': '0.9500', 'multiplierDecimal': '4', 'multiplierUp': '1.0500', 'filterType': 'PERCENT_PRICE'}, {'filterType': 'POSITION_RISK_CONTROL', 'positionControlSide': 'NONE'}], 'orderTypes': ['LIMIT', 'MARKET', 'STOP', 'STOP_MARKET', 'TAKE_PROFIT', 'TAKE_PROFIT_MARKET', 'TRAILING_STOP_MARKET'], 'timeInForce': ['GTC', 'IOC', 'FOK', 'GTX', 'GTD'], 'permissionSets': ['GRID', 'COPY', 'DCA']}



# class BinancePublicApi:
#     def __init__(self, info_handler: ErrorHandler):
#         info_handler.wrap_foreign_methods(self)
#         self.info_handler = info_handler

#         self.exchangeInfo_url = 'https://fapi.binance.com/fapi/v1/exchangeInfo'
#         self.klines_url = 'https://fapi.binance.com/fapi/v1/klines'
#         self.price_url = 'https://fapi.binance.com/fapi/v1/ticker/price'
#         self.fair_price_url = 'https://fapi.binance.com/fapi/v1/premiumIndex'

#         self.filtered_symbols: set[str] = set()  # сюда сохраним только USDT perpetual

#         self.instruments: dict[str, dict] = {}

#     async def update_filtered_symbols(self, session: aiohttp.ClientSession):
#         """Получаем список доступных торговых символов PERPETUAL USDT"""
#         try:
#             async with session.get(self.exchangeInfo_url) as response:
#                 if response.status != 200:
#                     self.info_handler.debug_error_notes(f"Failed to fetch exchange info: {response.status}")
#                     return
#                 data = await response.json()
#                 self.instruments = {
#                     item["symbol"]: item
#                     for item in data.get("symbols", [])
#                     if item.get("contractType") == "PERPETUAL"
#                     and item.get("status") == "TRADING"
#                     and item.get("quoteAsset") == "USDT"
#                 }
#                 self.filtered_symbols = set(self.instruments.keys())
#         except Exception as ex:
#             self.info_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name}")

#     # def get_precisions(self, symbol: str) -> tuple[int, int] | None:
#     #     symbol_data = self.instruments.get(symbol)
#     #     if not symbol_data:
#     #         return None

#     #     lot_size_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "LOT_SIZE"), None)
#     #     price_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "PRICE_FILTER"), None)

#     #     if not lot_size_filter or not price_filter:
#     #         return None

#     #     def count_decimal_places(number_str: str) -> int:
#     #         if '.' in number_str:
#     #             return len(number_str.rstrip('0').split('.')[-1])
#     #         return 0

#     #     qty_precision = count_decimal_places(lot_size_filter['stepSize'])
#     #     price_precision = count_decimal_places(price_filter['tickSize'])

#     #     return qty_precision, price_precision

#     def get_precisions(self, symbol: str) -> tuple[int, int, float, float] | None:
#         """
#         Возвращает кортеж:
#         (qty_precision, price_precision, max_leverage, max_notional_value)
#         """
#         symbol_data = self.instruments.get(symbol)
#         if not symbol_data:
#             return None
#         print(symbol_data)

#         lot_size_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "LOT_SIZE"), None)
#         price_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "PRICE_FILTER"), None)
#         leverage_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "LEVERAGE_FILTER"), None)
#         notional_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "MARKET_LOT_SIZE" or f["filterType"] == "NOTIONAL"), None)

#         if not lot_size_filter or not price_filter:
#             return None

#         def count_decimal_places(number_str: str) -> int:
#             if '.' in number_str:
#                 return len(number_str.rstrip('0').split('.')[-1])
#             return 0

#         qty_precision = count_decimal_places(lot_size_filter['stepSize'])
#         price_precision = count_decimal_places(price_filter['tickSize'])

#         # maxLeverage может быть прямо в данных символа
#         max_leverage = float(symbol_data.get("maxLeverage", 0.0))
#         if leverage_filter and leverage_filter.get("maxLeverage"):
#             max_leverage = float(leverage_filter["maxLeverage"])

#         # Для notional фильтра — берём максимальный номинал (если доступен)
#         max_notional_value = 0.0
#         if notional_filter:
#             if "maxNotionalValue" in notional_filter:
#                 max_notional_value = float(notional_filter["maxNotionalValue"])
#             elif "notional" in notional_filter:
#                 max_notional_value = float(notional_filter["notional"])

#         # Иногда Binance возвращает список уровней плеча, можно выбрать максимальный
#         if isinstance(symbol_data.get("leverageBrackets"), list):
#             max_notional_value = max(
#                 (float(bracket.get("notionalCap", 0)) for bracket in symbol_data["leverageBrackets"]),
#                 default=max_notional_value
#             )
#             max_leverage = max(
#                 (float(bracket.get("initialLeverage", 0)) for bracket in symbol_data["leverageBrackets"]),
#                 default=max_leverage
#             )

#         return qty_precision, price_precision, max_leverage, max_notional_value



# import asyncio
# import aiohttp
# import time
# import hmac
# import hashlib
# from pprint import pprint

# # === ТВОИ КЛЮЧИ (захардкодил как просил) ===
# BINANCE_API_PUBLIC_KEY = "Vz2ImnNehZn8fCpsnUn7cUcaBCZ5TuS5RW4CqCUZH2pxcv9KUzCvXOgxJygXw1yc"
# BINANCE_API_PRIVATE_KEY = "h0uGoxCeDF9U2mk0NJvWvKld0rTsoV0pWFyCgqoH78NFRIicAXYf6KHkh6GCIitB"

# # === Тестовая функция ===
# async def test_leverage_brackets():
#     url = "https://fapi.binance.com/fapi/v1/leverageBracket"
    
#     timestamp = int(time.time() * 1000)
#     params = f"timestamp={timestamp}"
#     signature = hmac.new(
#         BINANCE_API_PRIVATE_KEY.encode('utf-8'),
#         params.encode('utf-8'),
#         hashlib.sha256
#     ).hexdigest()

#     query_string = f"{params}&signature={signature}"
#     full_url = f"{url}?{query_string}"
#     headers = {'X-MBX-APIKEY': BINANCE_API_PUBLIC_KEY}

#     print(f"Запрос: {full_url}\n")
    
#     async with aiohttp.ClientSession() as session:
#         async with session.get(full_url, headers=headers) as resp:
#             print(f"Статус: {resp.status}")
#             if resp.status == 401:
#                 print("ОШИБКА: 401 — неверные ключи или IP не в whitelist")
#                 return
#             if resp.status != 200:
#                 text = await resp.text()
#                 print(f"Ошибка {resp.status}: {text}")
#                 return

#             data = await resp.json()
#             print(f"Получено объектов: {len(data)}\n")
            
#             # Покажем только популярные + CELOUSDT (как у тебя был)
#             targets = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "CELOUSDT"]
#             for item in data:
#                 if item["symbol"] in targets:
#                     print(f"\n=== {item['symbol']} ===")
#                     brackets = item["brackets"]
#                     print(f"Макс. плечо: {brackets[0]['initialLeverage']}x")
#                     print(f"Макс. номинал: {brackets[-1]['notionalCap']:,} USDT")
#                     print("Все скобки:")
#                     for b in brackets:
#                         print(f"  {b['initialLeverage']:3}x → до {b['notionalCap']:12,} USDT (bracket {b['bracket']})")

#             # Сохраним весь ответ в файл (полезно)
#             import json
#             with open("leverage_brackets_full.json", "w", encoding="utf-8") as f:
#                 json.dump(data, f, indent=2, ensure_ascii=False)
#             print(f"\nПолный ответ сохранён в leverage_brackets_full.json")

# # === Запуск ===
# if __name__ == "__main__":
#     asyncio.run(test_leverage_brackets())




    # def get_precisions(self, symbol: str) -> tuple[int, int, float, float] | None:
    #     """
    #     Возвращает кортеж:
    #     (qty_precision, price_precision, max_leverage, max_notional_value)
    #     """
    #     symbol_data = self.instruments.get(symbol)
    #     if not symbol_data:
    #         return None
    #     print(symbol_data)

    #     lot_size_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "LOT_SIZE"), None)
    #     price_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "PRICE_FILTER"), None)
    #     leverage_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "LEVERAGE_FILTER"), None)
    #     notional_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "MARKET_LOT_SIZE" or f["filterType"] == "NOTIONAL"), None)

    #     if not lot_size_filter or not price_filter:
    #         return None

    #     def count_decimal_places(number_str: str) -> int:
    #         if '.' in number_str:
    #             return len(number_str.rstrip('0').split('.')[-1])
    #         return 0

    #     qty_precision = count_decimal_places(lot_size_filter['stepSize'])
    #     price_precision = count_decimal_places(price_filter['tickSize'])

    #     # maxLeverage может быть прямо в данных символа
    #     max_leverage = float(symbol_data.get("maxLeverage", 0.0))
    #     if leverage_filter and leverage_filter.get("maxLeverage"):
    #         max_leverage = float(leverage_filter["maxLeverage"])

    #     # Для notional фильтра — берём максимальный номинал (если доступен)
    #     max_notional_value = 0.0
    #     if notional_filter:
    #         if "maxNotionalValue" in notional_filter:
    #             max_notional_value = float(notional_filter["maxNotionalValue"])
    #         elif "notional" in notional_filter:
    #             max_notional_value = float(notional_filter["notional"])

    #     # Иногда Binance возвращает список уровней плеча, можно выбрать максимальный
    #     if isinstance(symbol_data.get("leverageBrackets"), list):
    #         max_notional_value = max(
    #             (float(bracket.get("notionalCap", 0)) for bracket in symbol_data["leverageBrackets"]),
    #             default=max_notional_value
    #         )
    #         max_leverage = max(
    #             (float(bracket.get("initialLeverage", 0)) for bracket in symbol_data["leverageBrackets"]),
    #             default=max_leverage
    #         )

    #     return qty_precision, price_precision, max_leverage, max_notional_value


    # def get_max_notional_at_max_leverage(self, symbol: str) -> float:
    #     """
    #     Возвращает максимальный номинал (в USDT) при использовании максимального плеча.
    #     Например: для CELOUSDT → 5000.0
    #     """
    #     data = self.leverage_brackets.get(symbol)
    #     if not data:
    #         return 0.0
    #     return data["max_notional_at_max_leverage"]

    # def get_max_leverage(self, symbol: str) -> float:
    #     """Просто максимальное плечо"""
    #     data = self.leverage_brackets.get(symbol)
    #     if not data:
    #         return 0.0
    #     return data["max_leverage"]


# import asyncio
# import aiohttp
# # from datetime import datetime
# import aiohttp
# # import time
# import asyncio
# import inspect
# import random
# from typing import *
# from c_log import ErrorHandler, log_time
# import inspect
# # from pprint import pprint
# from typing import *
# from c_log import ErrorHandler, log_time
# from MANAGERS.online import NetworkManager
# import random
# # from pprint import pprint
# import traceback


# # DIFF_PCT: float = 4.9 # %
# DIFF_PCT: float = 4.9 # %
# PARSER_FREQUENTCY: float = 5 # sec
# CACHE_TTL: int= 29 * 60  # 5 минут
# TG_BOT_TOKEN = "8287838939:AAHNUiNy4reI7-9D1N0PXHBdVX9EJ4Xx04A"
# CHAT_ID_1 = "-1003036628247"



# class BinancePublicApi2:
#     def __init__(self, error_handler: ErrorHandler, proxy_url: str = None):
#         error_handler.wrap_foreign_methods(self)
#         self.error_handler = error_handler

#         self.exchangeInfo_url = 'https://fapi.binance.com/fapi/v1/exchangeInfo'
#         self.klines_url = 'https://fapi.binance.com/fapi/v1/klines'
#         self.price_url = 'https://fapi.binance.com/fapi/v1/ticker/price'
#         self.fair_price_url = 'https://fapi.binance.com/fapi/v1/premiumIndex'

#         self.proxy_url = proxy_url
#         self.filtered_symbols: set[str] = set()  # сюда сохраним только USDT perpetual

#         self.instruments: dict[str, dict] = {}


#     async def update_filtered_symbols(self, session: aiohttp.ClientSession):
#         """Получаем список доступных торговых символов PERPETUAL USDT"""
#         try:
#             async with session.get(self.exchangeInfo_url, proxy=self.proxy_url) as response:
#                 if response.status != 200:
#                     self.error_handler.debug_error_notes(f"Failed to fetch exchange info: {response.status}")
#                     return
#                 data = await response.json()
#                 self.instruments = {
#                     item["symbol"]: item
#                     for item in data.get("symbols", [])
#                     if item.get("contractType") == "PERPETUAL"
#                     and item.get("status") == "TRADING"
#                     and item.get("quoteAsset") == "USDT"
#                 }
#                 self.filtered_symbols = set(self.instruments.keys())
#         except Exception as ex:
#             self.error_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name}")

#     def get_precisions(self, symbol: str) -> tuple[int, int] | None:
#         symbol_data = self.instruments.get(symbol)
#         if not symbol_data:
#             return None

#         lot_size_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "LOT_SIZE"), None)
#         price_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "PRICE_FILTER"), None)

#         if not lot_size_filter or not price_filter:
#             return None

#         def count_decimal_places(number_str: str) -> int:
#             if '.' in number_str:
#                 return len(number_str.rstrip('0').split('.')[-1])
#             return 0

#         qty_precision = count_decimal_places(lot_size_filter['stepSize'])
#         price_precision = count_decimal_places(price_filter['tickSize'])

#         return qty_precision, price_precision

#     async def get_all_hot_prices(self, session: aiohttp.ClientSession) -> dict[str, float] | None:
#         """Возвращает все текущие цены для фильтрованных символов"""
#         try:
#             async with session.get(self.price_url, proxy=self.proxy_url) as response:
#                 if response.status != 200:
#                     self.error_handler.debug_error_notes(f"Failed to fetch all prices: {response.status}")
#                     return None
#                 data = await response.json()
#                 return {
#                     item["symbol"]: float(item["price"])
#                     for item in data
#                     if item["symbol"] in self.filtered_symbols
#                 }
#         except Exception as ex:
#             self.error_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name}")
#             return None

#     async def get_all_fair_prices(self, session: aiohttp.ClientSession) -> dict[str, float] | None:
#         """Возвращает все справедливые цены для фильтрованных символов"""
#         try:
#             async with session.get(self.fair_price_url, proxy=self.proxy_url) as response:
#                 if response.status != 200:
#                     self.error_handler.debug_error_notes(f"Failed to fetch fair prices: {response.status}")
#                     return None
#                 data = await response.json()
#                 return {
#                     item["symbol"]: float(item["markPrice"])
#                     for item in data
#                     if item["symbol"] in self.filtered_symbols
#                 }
#         except Exception as ex:
#             self.error_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name}")
#             return None


# class TelegramNotifier():
#     def __init__(
#             self,
#             token: str,
#             chat_ids: list[int],
#             info_handler: ErrorHandler
#         ):
#         self.token = token
#         self.chat_ids = [x.strip() for x in chat_ids if x and isinstance(x, str)]
#         self.base_tg_url = f"https://api.telegram.org/bot{self.token}"
#         self.send_text_endpoint = "/sendMessage"
#         self.send_photo_endpoint = "/sendPhoto"
#         self.delete_msg_endpoint = "/deleteMessage"

#         info_handler.wrap_foreign_methods(self)
#         self.info_handler = info_handler
#         self.report_list = []

#     async def send_report_batches(self, is_send: bool = True, batch_size: int = 1):
#         """Отправляет накопленные сообщения в TG пачками по batch_size, удаляя их только после отправки."""
#         if not isinstance(batch_size, int) or batch_size < 1:
#             print(f"[ERROR] Invalid batch_size={batch_size!r}: must be int >= 1")
#             return

#         while self.report_list:
#             # Чистим список от пустых значений, не меняя ссылку
#             self.report_list[:] = [
#                 x for x in self.report_list
#                 if isinstance(x, str) and x.strip()
#             ]

#             if not self.report_list:
#                 break

#             batch = self.report_list[:batch_size]
#             text_block = "\n\n".join(batch)

#             try:
#                 if is_send:
#                     await self.send(
#                         text=text_block,
#                         photo_bytes=None,
#                         disable_notification=False
#                     )
#             except Exception as e:
#                 print(f"[ERROR][TG send]: {e} ({log_time()})")

#             # Удаляем только отправленные сообщения
#             del self.report_list[:len(batch)]
#             await asyncio.sleep(0.25)

#     async def send(
#         self,
#         text: str,
#         photo_bytes: bytes = None,
#         disable_notification: bool = False,
#         max_retries: int = float("inf"),
#     ):
#         """
#         Отправка сообщения с авто-реконнектом и повторными попытками.
#         """

#         async def _try_send(session: aiohttp.ClientSession, chat_id):
#             if photo_bytes:
#                 url = self.base_tg_url + self.send_photo_endpoint
#                 data = aiohttp.FormData()
#                 data.add_field("chat_id", str(chat_id))
#                 data.add_field("caption", text or "")
#                 data.add_field("parse_mode", "HTML")
#                 data.add_field("disable_web_page_preview", "true")
#                 data.add_field("disable_notification", str(disable_notification).lower())
#                 data.add_field("photo", photo_bytes, filename="spread.png", content_type="image/png")
#             else:
#                 url = self.base_tg_url + self.send_text_endpoint
#                 data = {
#                     "chat_id": chat_id,
#                     "text": text,
#                     "parse_mode": "HTML",
#                     "disable_web_page_preview": True,
#                     "disable_notification": disable_notification,
#                 }

#             # Повторные попытки с backoff
#             attempt = 0
#             while True:
#                 attempt += 1
#                 try:
#                     async with session.post(url, data=data, timeout=10) as resp:
#                         if resp.status != 200:
#                             err_text = await resp.text()
#                             raise Exception(f"HTTP {resp.status}: {err_text}")

#                         # response_json = await resp.json()
#                         # message_id = response_json.get("result", {}).get("message_id")
#                         return True  # успех

#                 except Exception as e:
#                     wait_time = random.uniform(1, 3)  # backoff
#                     if self.info_handler:
#                         self.info_handler.debug_error_notes(
#                             f"[TelegramSender] Попытка {attempt}/{max_retries} не удалась ({e}), "
#                             f"повтор через {wait_time:.1f}с",
#                             is_print=True,
#                         )
#                     if attempt == max_retries:
#                         return False
#                     await asyncio.sleep(wait_time)

#         # Новый session для каждой пачки отправок
#         async with aiohttp.ClientSession() as session:
#             tasks = [_try_send(session, chat_id) for chat_id in self.chat_ids]
#             results = await asyncio.gather(*tasks, return_exceptions=True)
#             return all(r is True for r in results)        


# class Formatter:
#     @staticmethod
#     def format_coins_for_tg(coins: List[Dict], title: str = f"Монеты с fair > last и diff >= {DIFF_PCT}%") -> str:
#         """
#         Форматирует список монет для Telegram.
#         coins: [{"symbol": str, "last_price": float, "fair_price": float, "diff_percent": float, "price_precision": int}, ...]
#         """
#         if not coins:
#             return "❌ Нет монет с fair > last и отклонением >= 5%"

#         lines = [f"💹 {title} ({len(coins)} шт):\n"]
#         for c in coins:
#             prec = c.get('price_precision', 2)  # default to 2 if not available
#             lines.append(
#                 f"• {c['symbol']}: last={c['last_price']:.{prec}f}, fair={c['fair_price']:.{prec}f}, "
#                 f"diff={c['diff_percent']:.2f}%"
#             )
#         return "\n".join(lines)
    

# class Core:
#     def __init__(self):
#         self.error_handler = ErrorHandler()
#         self.binance_public = BinancePublicApi2(
#             error_handler=self.error_handler,
#             proxy_url=None
#         )
#         self.publuc_connector = NetworkManager(
#             error_handler=self.error_handler,
#             proxy_url=None, user_label="public"
#         )

#         self.notifier = TelegramNotifier(
#             token=TG_BOT_TOKEN,
#             chat_ids=[CHAT_ID_1],
#             info_handler=self.error_handler
#         )

#         # Кеш для монет: symbol -> timestamp последнего отчета
#         self.coins_cache: dict[str, float] = {}

#     async def _run(self):

#         if not await self.publuc_connector.validate_session():
#             self.error_handler.debug_error_notes(
#                 f'[ERROR][public]: проблемы с инициализацией сессии'
#             )
#             raise RuntimeError("Failed to initialize session for 'public'")

#         await self.publuc_connector.initialize_session()
#         self.public_session: aiohttp.ClientSession = self.publuc_connector.session

#         # Получаем фильтрованные символы
#         await self.binance_public.update_filtered_symbols(self.public_session)

#         while True:
#             try:
#                 all_hot = await self.binance_public.get_all_hot_prices(self.public_session)
#                 all_fair = await self.binance_public.get_all_fair_prices(self.public_session)

#                 if not all_hot or not all_fair:
#                     print("❌ Ошибка получения цен")
#                     await asyncio.sleep(PARSER_FREQUENTCY)
#                     continue

#                 now = asyncio.get_event_loop().time()

#                 # Очистка устаревшего кеша: удаляем записи старше CACHE_TTL
#                 self.coins_cache = {
#                     sym: ts for sym, ts in self.coins_cache.items()
#                     if now - ts < CACHE_TTL
#                 }

#                 coins_to_report = []

#                 for symbol in all_hot.keys():
#                     last_price = all_hot.get(symbol)
#                     fair_price = all_fair.get(symbol)

#                     if last_price is None or fair_price is None:
#                         continue

#                     diff_percent = (fair_price - last_price) / last_price * 100
#                     precisions = self.binance_public.get_precisions(symbol)
#                     price_precision = precisions[1] if precisions else 2
#                     coin_data = {
#                         "symbol": symbol,
#                         "last_price": last_price,
#                         "fair_price": fair_price,
#                         "diff_percent": round(diff_percent, 2),
#                         "price_precision": price_precision
#                     }

#                     # Проверяем условие и кеш: отчет только если условие выполняется и прошло CACHE_TTL с последнего отчета
#                     if fair_price > last_price and diff_percent >= DIFF_PCT:
#                         cached_ts = self.coins_cache.get(symbol)
#                         if cached_ts is None or now - cached_ts >= CACHE_TTL:
#                             coins_to_report.append(coin_data)
#                             self.coins_cache[symbol] = now

#                 # Форматируем и отправляем сообщение через Formatter + TelegramNotifier
#                 if coins_to_report:
#                     report_text = Formatter.format_coins_for_tg(coins_to_report)
#                     print(report_text)
#                     self.notifier.report_list.append(report_text)
#                     await self.notifier.send_report_batches(batch_size=1)

#             except Exception as ex:
#                 tb = traceback.format_exc()
#                 self.error_handler.debug_error_notes(
#                     f"[_run.main.py]: Ошибка в главном цикле: {ex}/{tb}", is_print=True
#                 )

#             await asyncio.sleep(PARSER_FREQUENTCY)



# async def main():
#     instance = Core()
#     try:
#         await instance._run()
#     except asyncio.CancelledError:
#         print("🚩 Асинхронная задача была отменена.")
#     except KeyboardInterrupt:
#         print("\n⛔ Остановка по Ctrl+C")
#     # except Exception as e:
#     #     print(f"\n❌ Ошибка: {type(e).__name__} — {e}")
#     finally:
#         await instance.publuc_connector.shutdown_session()  # ← добавь это
#         print("Сессии закрываются...")


# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         pass


# class FairSignalDetector:
#     """Отслеживает расхождение справедливой и горячей цены с подтверждением по количеству или времени."""

#     def __init__(self):
#         self.signals_cache: Dict[str, Dict] = {}  # {symbol: {"first_time": float, "count": int}}
#         self.signal_symbols: Set = set()
#         self.diff_pct = abs(DIFF_PCT) if DIFF_PCT else 5.0

#     def check(self, all_hot: dict, all_fair: dict) -> Optional[str]:
#         """
#         Проверяет все символы и возвращает символ, по которому сигнал подтвержден.
#         Возвращает None, если сигнала нет или не подтвержден.
#         """
#         if not all_hot or not all_fair:
#             return None

#         now = time.time()

#         for symbol, last_price in all_hot.items():
#             # скипаем символ так как он уже. Чистим структуру на внешней стороне после отработки
#             if symbol in self.signal_symbols:
#                 continue

#             fair_price = all_fair.get(symbol)
#             if last_price is None or fair_price is None:
#                 continue

#             diff_percent = (fair_price - last_price) / last_price * 100

#             # --- основное условие ---
#             if diff_percent >= self.diff_pct: # fair_price > last_price -- уже заложено в условии
#                 record = self.signals_cache.get(symbol)

#                 # первый сигнал
#                 if not record:
#                     self.signals_cache[symbol] = {"first_time": now, "count": 0, "toggle": True}    

#                 # проверка по времени удержания сигнала
#                 if SIGNAL_TTL > 0 and (now - record["first_time"]) >= SIGNAL_TTL:
#                     del self.signals_cache[symbol]
#                     self.signal_symbols.add(symbol)
#                     return symbol       

#                 # # инкремент повторов
#                 # if not self.signals_cache[symbol]["toggle"]:
#                 #     record["count"] += 1

#                 # # проверка по количеству подтверждений
#                 # if CONFIRM_SIGNAL > 1 and record["count"] >= CONFIRM_SIGNAL:                    
#                 #     del self.signals_cache[symbol]
#                 #     self.signal_symbols.add(symbol)
#                 #     return symbol
                
#                 # self.signals_cache[symbol]["toggle"] = True

#             # --- если сигнал временно исчез ---
#             else:
#                 if symbol in self.signals_cache:
#                     # self.signals_cache[symbol]["count"] -= 1
#                     # self.signals_cache[symbol]["toggle"] = False
#                     self.signals_cache[symbol]["first_time"] = now

#         return None



    # async def _run(self):
    #     self.info_handler.debug_info_notes(f"[INFO] ✨ Бот начал работу.")

    #     ok, _ = await self.public_connector.validate_session()
    #     if not ok:
    #         raise RuntimeError("Failed to initialize session for 'public'")

    #     await self.public_connector.start_ping_loop()
    #     self.public_session: aiohttp.ClientSession = self.public_connector.session

    #     await self.binance_private.set_hedge_mode(self.public_session)
    #     await asyncio.sleep(1)

    #     signal_updating_time     = time.monotonic()
    #     status_pos_updating_time = time.monotonic()
    #     last_write_logs_time     = time.monotonic()

    #     first_pos_update: bool = True

    #     asyncio.create_task(self.symbols_state_updater(self.public_session))        
    #     try:
    #         await asyncio.wait_for(self.symbols_state_event.wait(), timeout=30.0)
    #         self.info_handler.debug_info_notes("Leverage brackets и символы загружены")
    #     except asyncio.TimeoutError:
    #         self.info_handler.debug_info_notes("Таймаут загрузки brackets — продолжаем (обновятся в фоне)")

    #     while not self.stop_bot:
    #         try:
    #             now = time.monotonic()
    #             if now - signal_updating_time >= SIGNAL_FREQUENCY:
    #                 try:                
    #                     # Получаем цены прямым запосом
    #                     all_hot = await self.binance_public.get_all_hot_prices(self.public_session)
    #                     all_fair = await self.binance_public.get_all_fair_prices(self.public_session)

    #                     if not all_hot or not all_fair:
    #                         self.info_handler.debug_info_notes(f"❌ Ошибка получения цен.")
    #                         await asyncio.sleep(0)
    #                         continue                

    #                     signal = await self.signal_detector.check(all_hot, all_fair, self.position_vars, self.pos_vars_lock)
    #                     if signal:
    #                         pos_limit_flag: bool = (
    #                             POSITION_LIMIT is not None
    #                             and sum(
    #                                 1 for x in (self.position_vars or {}).values()
    #                                 if isinstance(x, dict) and x.get("in_position", False)
    #                             ) >= POSITION_LIMIT
    #                         )

    #                         if pos_limit_flag:
    #                             print("Сработал ограничитель числа позиций")
    #                             continue

    #                         print("if signal:")
    #                         signal_symbol, diff_percent = signal
    #                         clines = await self.binance_public.get_klines_basic(
    #                             session=self.public_session,
    #                             symbol=signal_symbol,
    #                             interval=self.signal_confirm.tf,
    #                             limit=int(self.signal_confirm.slow * 2.5),
    #                         )

    #                         trend = self.signal_confirm.detect_trend(clines)
    #                         # print(trend)
    #                         if trend is None or trend == "UP":
    #                             # проверка на инпозицию:
    #                             # if self.public_session and not self.public_session.closed:
    #                             open_positions = await self.binance_private.get_open_positions(session=self.public_session)
    #                             in_position = has_open_position(open_positions, signal_symbol, "LONG")
    #                             if in_position is False:
    #                                 msg = "📈 Тренд подтверждён." if TREND_LINE.get(self.signal_confirm.tf, {}).get("enable") \
    #                                     else "📈 Подтверждение тренда не требуется."
    #                                 self.info_handler.debug_info_notes(f"Сигнал по монете {signal_symbol}. {msg}")

    #                                 last_price = all_hot.get(signal_symbol)
    #                                 fair_price = all_fair.get(signal_symbol)

    #                                 precisions = self.binance_public.get_precisions(signal_symbol)
    #                                 price_precision = precisions[1] if precisions else 2

    #                                 signal_data = {
    #                                     "symbol": signal_symbol,
    #                                     "last_price": last_price,
    #                                     "fair_price": fair_price,
    #                                     "diff_percent": round(diff_percent, 2),
    #                                     "price_precision": price_precision
    #                                 }
    #                                 report_text = Formatter.format_coins_for_tg(signal_data) or ""
    #                                 asyncio.create_task(self.notifier.send(text=report_text))
                                    
    #                                 await self.set_order_template(session=self.public_session, symbol=signal_symbol, cur_price=last_price)

    #                             elif in_position is True:
    #                                 print(f"Сигнал не обрабатываем. Монета {signal_symbol} уже в позиции")
    #                         else:
    #                             self.info_handler.debug_info_notes(f"📈 Тренд НЕ подтверждён для {signal_symbol}. Пропускаем сигнал. ")
    #                 finally:
    #                     signal_updating_time = now

    #             now = time.monotonic()
    #             if now - status_pos_updating_time >= UPDATE_POSITION_FREQUENCY or first_pos_update:
    #                 try:
    #                     # if self.public_session and not self.public_session.closed:
    #                     open_positions = await self.binance_private.get_open_positions(session=self.public_session)

    #                     for symbol in list(self.position_vars.keys()):   
    #                         # print(self.position_vars[symbol])
    #                         in_position = has_open_position(open_positions, symbol, "LONG")                        
    #                         if in_position is True:
    #                             async with self.pos_vars_lock:
    #                                 self.position_vars[symbol]["in_position"] = True  

    #                         elif in_position is False:
    #                             # if self.position_vars.get(symbol, {}).get("in_position"):
    #                             await self.cancel_order_template(                               
    #                                 session=self.public_session,
    #                                 strategy_name=STRATEGY_NAME,
    #                                 symbol=symbol,
    #                                 suffix="tp"
    #                             )
    #                             async with self.pos_vars_lock:
    #                                 self.position_vars[symbol]["in_position"] = False
    #                                 if symbol in self.signal_detector.signals_cache:
    #                                     del self.signal_detector.signals_cache[symbol]
    #                                 self.signal_detector.signal_symbols.discard(symbol)

    #                 finally:
    #                     status_pos_updating_time = now
    #                     first_pos_update = False

    #         except Exception as ex:
    #             tb = traceback.format_exc()
    #             self.info_handler.debug_error_notes(
    #                 f"[_run.main.py]: Ошибка в главном цикле: {ex}/{tb}", is_print=True
    #             )

    #         finally:
    #             if WRITE_TO_LOG:
    #                 now = time.monotonic()
    #                 if now - last_write_logs_time >= WRITE_LOGS_INTERVAL:
    #                     try:
    #                         await self.write_log.write_logs()
    #                     except Exception as e:
    #                         self.info_handler.debug_error_notes(f"Ошибка при записи логов: {e}")
    #                     last_write_logs_time = now
    #             await asyncio.sleep(MAIN_FREQUENTCY)



    # async def set_order_template(
    #         self,
    #         session:   aiohttp.ClientSession,
    #         symbol:    str,
    #         cur_price: float,
    #         debug: bool = True
    #     ) -> Optional[bool]:

    #     debug_label = f"[{USER_NAME}][{STRATEGY_NAME}][{symbol}][LONG]"
    #     prec = self.binance_public.get_precisions(symbol)
    #     if not prec:
    #         self.info_handler.debug_error_notes(f"[{debug_label}] Нет данных по фильтрам {symbol}")
    #         return False
    #     qty_precision, price_precision = prec

    #     trade_spec = self.binance_private.leverage_brackets.get(symbol)
    #     if not trade_spec:
    #         self.info_handler.debug_error_notes(f"[{debug_label}] Нет leverage_brackets для {symbol}")
    #         return False
    #     max_leverage, max_notional_value = trade_spec.get("max_leverage"), trade_spec.get("max_notional")

    #     if debug:
    #         print(
    #             f"[PRECISIONS]\n"
    #             f"  Qty precision:     {qty_precision}\n"
    #             f"  Price precision:   {price_precision}\n"
    #             f"  Max leverage:      {max_leverage}\n"
    #             f"  Max notional:      {max_notional_value}"
    #         )
    
    #     leverage = FORCE_LEVERAGE or max_leverage      

    #     if symbol not in self.secondary_cache:
    #         self.secondary_cache.add(symbol)
            
    #         await self.binance_private.set_margin_type(session=session, strategy_name=STRATEGY_NAME,
    #                                                 symbol=symbol, margin_type=self.margin_type)
    #         await self.binance_private.set_leverage(session=session, strategy_name=STRATEGY_NAME,
    #                                                 symbol=symbol, lev_size=leverage)
    #     plane_size1 = 0
    #     # === выбор маржи ===
    #     if FORCE_MARGIN:
    #         # если явно задано — используем фиксированную маржу
    #         plane_size1 = FORCE_MARGIN * leverage
    #     # else:
    #     # авторасчёт с ограничением по notional и лимиту маржи
    #     allowed_by_notional = max_notional_value * SIZE_FACTOR / 100
    #     allowed_by_margin   = (MARGIN_LIMIT * leverage) if MARGIN_LIMIT else float("inf")
    #     plane_size2         = min(allowed_by_notional, allowed_by_margin)

    #     plane_size = plane_size1 or plane_size2

    #     # === контроль доступного баланса ===
    #     required_usdt = plane_size / leverage + MARGIN_BUFER  # safety buffer
    #     available_usdt = await self.binance_private.get_avi_balance(session=session)

    #     margin_size = min(available_usdt, required_usdt)

    #     async with self.pos_vars_lock:
    #         self.position_vars.setdefault(symbol, {"in_position": False, "tp_order_id": None})

    #     qty = qty_calc(
    #         margin_size=margin_size,
    #         entry_price=cur_price,
    #         leverage=leverage,
    #         volume_rate=100,
    #         precision=qty_precision,
    #         debug_label=debug_label
    #     )

    #     if not qty:
    #         self.info_handler.debug_info_notes(f"[CRITICAL][{debug_label}] Ошибка при расчете количества актива позиции.")
    #         return False

    #     order_start_time = time.monotonic()
    #     market_order_result = await self.binance_private.make_order(
    #         session=session,
    #         strategy_name=STRATEGY_NAME,
    #         symbol=symbol,
    #         qty=qty,
    #         side="BUY",
    #         position_side="LONG",
    #         market_type="MARKET"
    #     )
    #     self.info_handler.debug_info_notes(f"[INFO][{debug_label}] Try to complite make_order in {time.monotonic() - order_start_time:.2f}s")

    #     ok, order_details = self.order_validator.validate_market_response(
    #         market_order_result[0], debug_label
    #     )

    #     exequted_price = order_details.get("price")

    #     if not ok or not exequted_price:
    #         self.info_handler.debug_info_notes(f"[CRITICAL][{debug_label}] Не удалось нормально открыть ордер.")
    #         return
        
    #     async with self.pos_vars_lock:
    #         self.position_vars[symbol]["in_position"] = True

    #     print(f"✅ Открыт ордер {symbol} по цене {exequted_price}")

    #     # set TP:
    #     target_price = round(exequted_price * (1 + TP/ 100), price_precision)

    #     try:
    #         response = await self.binance_private.place_risk_order(
    #             session=session,
    #             strategy_name=STRATEGY_NAME,
    #             symbol=symbol,
    #             qty=qty,
    #             side="SELL",
    #             position_side="LONG",
    #             target_price=target_price,
    #             suffix="tp",
    #             order_type=self.risk_order_type
    #         )
    #     except Exception as e:
    #         self.info_handler.debug_info_notes(f"[CRITICAL][{debug_label}] Error placing TP order: {e}")
    #         return False

    #     risk_details = self.order_validator.validate_risk_response(response, "TP", debug_label)
    #     self.info_handler.debug_info_notes(f"[INFO][{debug_label}] TP validation result: {risk_details}")
    #     if risk_details:
    #         ok_risk, order_id = risk_details
    #         if ok_risk:   
    #             async with self.pos_vars_lock:             
    #                 self.position_vars[symbol]["tp_order_id"] = order_id
    #             self.info_handler.debug_info_notes(f"[INFO][{debug_label}] TP order placed: order_id={order_id}")
    #             return True  



        # self.info_handler.debug_error_notes("🔥 TEST: direct write to error list")
        # self.info_handler.debug_info_notes("ℹ️ TEST: direct write to info list")
        # await self.write_log.write_logs()
        # return




# BASE_DIR = Path(__file__).resolve().parents[1]  # до корня проекта

# DEBUG_DIR = BASE_DIR / "INFO" / "DEBUG"
# TRADES_DIR = BASE_DIR / "INFO" / "TRADES"

# DEBUG_ERR_FILE = DEBUG_DIR / "error_.txt"
# DEBUG_INFO_FILE = DEBUG_DIR / "info_.txt"
# TRADES_INFO_FILE = TRADES_DIR / "info_.txt"
# TRADES_SECONDARY_FILE = TRADES_DIR / "secondary_.txt"
# TRADES_FAILED_FILE = TRADES_DIR / "failed_.txt"
# TRADES_SUCC_FILE = TRADES_DIR / "success_.txt"