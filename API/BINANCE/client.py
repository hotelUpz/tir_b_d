# API.BINANCE.client.py

import asyncio
import aiohttp
from typing import *
import random
import time
import hmac
import hashlib
import pandas as pd
from c_log import ErrorHandler, log_time
from c_validators import HTTP_Validator
import inspect
# import traceback


class BinancePublicApi:
    def __init__(self, info_handler: ErrorHandler):
        info_handler.wrap_foreign_methods(self)
        self.info_handler = info_handler

        self.exchangeInfo_url = 'https://fapi.binance.com/fapi/v1/exchangeInfo'
        self.klines_url = 'https://fapi.binance.com/fapi/v1/klines'
        self.price_url = 'https://fapi.binance.com/fapi/v1/ticker/price'
        self.fair_price_url = 'https://fapi.binance.com/fapi/v1/premiumIndex'

        self.filtered_symbols: set[str] = set()  # сюда сохраним только USDT perpetual

        self.instruments: dict[str, dict] = {}

    async def update_filtered_symbols(self, session: aiohttp.ClientSession):
        """Получаем список доступных торговых символов PERPETUAL USDT"""
        try:
            async with session.get(self.exchangeInfo_url) as response:
                if response.status != 200:
                    self.info_handler.debug_error_notes(f"Failed to fetch exchange info: {response.status}")
                    return
                data = await response.json()
                self.instruments = {
                    item["symbol"]: item
                    for item in data.get("symbols", [])
                    if item.get("contractType") == "PERPETUAL"
                    and item.get("status") == "TRADING"
                    and item.get("quoteAsset") == "USDT"
                }
                self.filtered_symbols = set(self.instruments.keys())
        except Exception as ex:
            self.info_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name}")

    def get_precisions(self, symbol: str) -> tuple[int, int] | None:
        symbol_data = self.instruments.get(symbol)
        if not symbol_data:
            return None

        lot_size_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "LOT_SIZE"), None)
        price_filter = next((f for f in symbol_data["filters"] if f["filterType"] == "PRICE_FILTER"), None)

        if not lot_size_filter or not price_filter:
            return None

        def count_decimal_places(number_str: str) -> int:
            if '.' in number_str:
                return len(number_str.rstrip('0').split('.')[-1])
            return 0

        qty_precision = count_decimal_places(lot_size_filter['stepSize'])
        price_precision = count_decimal_places(price_filter['tickSize'])

        return qty_precision, price_precision

    async def get_all_hot_prices(self, session: aiohttp.ClientSession) -> dict[str, float] | None:
        """Возвращает все текущие цены для фильтрованных символов"""
        try:
            async with session.get(self.price_url) as response:
                if response.status != 200:
                    self.info_handler.debug_error_notes(f"Failed to fetch all prices: {response.status}")
                    return None
                data = await response.json()
                return {
                    item["symbol"]: float(item["price"])
                    for item in data
                    if item["symbol"] in self.filtered_symbols
                }
        except Exception as ex:
            self.info_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name}")
            return None

    async def get_all_fair_prices(self, session: aiohttp.ClientSession) -> dict[str, float] | None:
        """Возвращает все справедливые цены для фильтрованных символов"""
        try:
            async with session.get(self.fair_price_url) as response:
                if response.status != 200:
                    self.info_handler.debug_error_notes(f"Failed to fetch fair prices: {response.status}")
                    return None
                data = await response.json()
                return {
                    item["symbol"]: float(item["markPrice"])
                    for item in data
                    if item["symbol"] in self.filtered_symbols
                }
        except Exception as ex:
            self.info_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name}")
            return None

    async def get_klines_basic(
            self,
            session: aiohttp.ClientSession,
            symbol: str,
            interval: str,
            limit: int,
            api_key: str = None):
        """
        Загружает данные свечей (klines) для заданного символа и возвращает только колонку Close.
        """
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        headers = {"X-MBX-APIKEY": api_key} if api_key else {}

        try:
            async with session.get(self.klines_url, params=params, headers=headers) as response:
                if response.status != 200:
                    self.info_handler.debug_error_notes(
                        f"Failed to fetch klines: {response.status}, {await response.text()}, {symbol}"
                    )
                    return pd.DataFrame(columns=['Close'])

                klines = await response.json()
                if not klines:
                    return pd.DataFrame(columns=['Close'])

            # извлекаем колонку закрытия
            df = pd.DataFrame(klines)[[0, 4]]
            df.columns = ['Time', 'Close']
            df['Time'] = pd.to_datetime(df['Time'], unit='ms')
            df.set_index('Time', inplace=True)
            df['Close'] = df['Close'].astype(float)
            return df

        except Exception as ex:
            self.info_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name}")
            return pd.DataFrame(columns=['Close'])
    

class BinancePrivateApi(HTTP_Validator):
    def __init__(
            self,
            info_handler: ErrorHandler,
            api_key: str = None,
            api_secret: str = None,
            user_label: str = "Nik"
        ) -> None:
        super().__init__(info_handler)

        self.balance_url = 'https://fapi.binance.com/fapi/v2/balance'
        self.create_order_url = self.cancel_order_url = 'https://fapi.binance.com/fapi/v1/order'
        self.change_trade_mode = 'https://fapi.binance.com/fapi/v1/positionSide/dual'
        self.set_margin_type_url = 'https://fapi.binance.com/fapi/v1/marginType'
        self.set_leverage_url = 'https://fapi.binance.com/fapi/v1/leverage'  
        self.leverage_brackets_url = 'https://fapi.binance.com/fapi/v1/leverageBracket'      
        self.positions2_url = 'https://fapi.binance.com/fapi/v2/account'     

        self.api_key, self.api_secret = api_key, api_secret 
        self.user_label = user_label
        self.leverage_brackets: dict[str, dict] = {}  # symbol -> {"max_leverage": 75.0, "max_notional": 5000.0}  # лимит при МАКСИМАЛЬНОМ плече

    def get_signature(self, params: dict):
        params['timestamp'] = int(time.time() * 1000)
        params_str = '&'.join([f'{k}={v}' for k, v in params.items()])
        signature = hmac.new(bytes(self.api_secret, 'utf-8'), params_str.encode('utf-8'), hashlib.sha256).hexdigest()
        params['signature'] = signature
        return params

    # === ДОБАВЬ ЭТОТ МЕТОД В BinancePrivateApi ===
    async def update_leverage_brackets(self, session: aiohttp.ClientSession):
        """Загружает brackets для всех символов и кэширует max_notional при максимальном плече"""
        if not (self.api_key and self.api_secret):
            self.info_handler.debug_error_notes(f"[{self.user_label}] API key/secret missing → leverage brackets skipped")
            return

        params = self.get_signature({})
        headers = {"X-MBX-APIKEY": self.api_key}

        try:
            async with session.get(self.leverage_brackets_url, headers=headers, params=params) as resp:
                if resp.status == 401:
                    self.info_handler.debug_error_notes(f"[{self.user_label}] Invalid API key/secret (401)")
                    return
                if resp.status != 200:
                    text = await resp.text()
                    self.info_handler.debug_error_notes(f"[{self.user_label}] leverageBracket error {resp.status}: {text}")
                    return

                data = await resp.json()
                self.leverage_brackets.clear()

                for item in data:
                    symbol = item["symbol"]
                    brackets = item["brackets"]
                    if not brackets:
                        continue

                    # Максимальное плечо — всегда в первой скобке
                    max_lev = int(brackets[0]["initialLeverage"])
                    # Максимальный номинал при этом плече
                    max_notional = float(brackets[0]["notionalCap"])

                    self.leverage_brackets[symbol] = {
                        "max_leverage": max_lev,
                        "max_notional": max_notional  # max_notional_at_max_leverage
                    }

                # self.info_handler.debug_error_notes(
                #     f"[{self.user_label}] Leverage brackets updated: {len(self.leverage_brackets)} symbols"
                # )

        except Exception as ex:
            self.info_handler.debug_error_notes(f"[{self.user_label}] Exception in update_leverage_brackets: {ex}")

    # private methods:   
    async def get_avi_balance(
            self,
            session: aiohttp.ClientSession,
            quote_asset: str = "USDT"
        ) -> float:
        """Получает доступный баланс quote_asset на Binance Futures"""
        headers = {
            "X-MBX-APIKEY": self.api_key
        }

        params = self.get_signature({})  # Подписываем запрос

        async with session.get(self.balance_url, headers=headers, params=params) as response:

            if response.status != 200:
                self.info_handler.debug_error_notes(f"[{self.user_label}][ERROR][get_avi_balance]: {response.status}, {await response.text()}")
                return 0.0
            
            data = await response.json()
            for asset in data:
                if asset["asset"] == quote_asset:
                    return float(asset["availableBalance"])  # Возвращаем доступный баланс quote_asset

        return 0.0  # Если не нашли quote_asset  
        
    # async def fetch_positions(self, session: aiohttp.ClientSession):
    #     params = self.get_signature({'recvWindow': 20000})
    #     headers = {
    #         'X-MBX-APIKEY': self.api_key
    #     }
    #     async with session.get(self.positions2_url, headers=headers, params=params) as response:
    #         if response.status != 200:
    #             self.info_handler.debug_error_notes(f"[{self.user_label}]: Failed to fetch positions: {response.status}, {await response.text()}", True)
    #         return await response.json()      

    async def get_open_positions(self, session: aiohttp.ClientSession) -> Optional[dict]:
        url = f"https://fapi.binance.com/fapi/v2/positionRisk"

        headers = {
            'X-MBX-APIKEY': self.api_key
        }

        params = {}
        signed_params = self.get_signature(params)

        result = {"success": False, "positions": [], "error": None}

        try:
            async with session.get(url, headers=headers, params=signed_params) as resp:
                data = await resp.json()
                if resp.status == 200:
                    for pos in data:
                        if float(pos["positionAmt"]) != 0:
                            result["positions"].append({
                                "symbol": pos["symbol"],
                                "side": "LONG" if float(pos["positionAmt"]) > 0 else "SHORT",
                                "volume": abs(float(pos["positionAmt"])),
                                "avg_price": float(pos["entryPrice"]),
                                "liq_price": float(pos["liquidationPrice"]),
                                "leverage": float(pos["leverage"])
                            })
                    result["success"] = True
                else:
                    result["error"] = data
                    print(f"❌ Ошибка получения позиций: {resp.status}, {data}")
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Ошибка get_open_positions: {e}")
        return result  

    async def get_realized_pnl(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        direction: Optional[str] = None,  # "LONG"/"SHORT"
    ) -> tuple[float, float]:
        """
        Считает реализованный PnL за период по символу (Binance Futures).
        Поддерживает фильтрацию по направлению позиции ("LONG"/"SHORT").
        Делает до 7 реконнектов, пересоздавая сессию на каждой попытке.
        """
        params = {
            "symbol": symbol,
            "recvWindow": 20000
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        headers = {"X-MBX-APIKEY": self.api_key}
        rows = []
        max_retries = 7

        for attempt in range(1, max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://fapi.binance.com/fapi/v1/userTrades",
                        params=self.get_signature(params),
                        headers=headers
                    ) as resp:
                        if resp.status == 200:
                            rows = await resp.json()
                            break
                        else:
                            self.info_handler.debug_error_notes(
                                f"[get_realized_pnl][Binance] status={resp.status}, "
                                f"attempt={attempt}/{max_retries}"
                            )
            except Exception as e:
                self.info_handler.debug_error_notes(
                    f"[get_realized_pnl][Binance] {e}, attempt={attempt}/{max_retries}"
                )

            if attempt < max_retries:
                await asyncio.sleep(random.uniform(1, 2))

        if not rows:
            return 0.0, 0.0

        pnl_usdt = 0.0
        commission = 0.0

        for row in rows:
            try:
                ts = int(row.get("time", 0))
                if start_time and ts < start_time:
                    continue

                pos_side = row.get("positionSide", "").upper()
                if direction and pos_side != direction.upper():
                    continue

                pnl_usdt += float(row.get("realizedPnl", 0.0))
                commission += float(row.get("commission", 0.0))
            except Exception:
                continue

        return round(pnl_usdt, 4), round(commission, 4)
                
    async def set_hedge_mode(
            self,
            session: aiohttp.ClientSession,
            true_hedg: bool = True,
        ):
        try:
            params = {
                "dualSidePosition": str(true_hedg).lower(),            
            }
            headers = {
                'X-MBX-APIKEY': self.api_key
            }
            params = self.get_signature(params)
            async with session.post(self.change_trade_mode, headers=headers, params=params) as response:
                try:
                    resp_j = await response.json()
                except:
                    resp_j = await response.text()

                self.info_handler.trade_secondary_list.append(f"[{self.user_label}]: {resp_j}. Time: {log_time()}")          
           
        except Exception as ex:
            self.info_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name} at line {inspect.currentframe().f_lineno}")
   
    async def set_margin_type(
            self,
            session: aiohttp.ClientSession,
            strategy_name: str,
            symbol: str,
            margin_type: str
        ):
        try:
            params = {
                'symbol': symbol,
                'marginType': margin_type,
                'recvWindow': 20000,
                'newClientOrderId': 'CHANGE_MARGIN_TYPE'
            }
            headers = {
                'X-MBX-APIKEY': self.api_key
            }
            params = self.get_signature(params)
            async with session.post(self.set_margin_type_url, headers=headers, params=params) as response:
                await self.requests_logger(response, self.user_label, strategy_name, "set_margin_type", symbol)
        except Exception as ex:
            self.info_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name} at line {inspect.currentframe().f_lineno}")

    async def set_leverage(
            self,
            session: aiohttp.ClientSession,
            strategy_name: str,
            symbol: str,
            lev_size: int
        ):
        try:
            params = {
                'symbol': symbol,
                'recvWindow': 20000,
                'leverage': lev_size
            }
            headers = {
                'X-MBX-APIKEY': self.api_key
            }
            params = self.get_signature(params)
            async with session.post(self.set_leverage_url, headers=headers, params=params) as response:
                await self.requests_logger(response, self.user_label, strategy_name, "set_leverage", symbol)
            
        except Exception as ex:
            self.info_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name} at line {inspect.currentframe().f_lineno}")

    async def make_order(
            self,
            session: aiohttp.ClientSession,
            strategy_name: str,
            symbol: str,
            qty: float,
            side: str,
            position_side: str,
            market_type: str = "MARKET"
        ):
        # try:
        #     mess = "Параметры запроса ордера:...\n"
        #     mess += f"{strategy_name}\n, {api_key}\n, {api_secret}\n, {symbol}\n, {qty}\n, {side}\n, {position_side}\n"
        #     self.info_handler.debug_info_notes(mess, True)
        # except:
        #     passs
        try:
            params = {
                "symbol": symbol,
                "side": side,
                "type": market_type,
                "quantity": abs(qty) if qty else 0.0,
                "positionSide": position_side,
                "recvWindow": 20000,
                "newOrderRespType": 'RESULT'
            }
            headers = {
                'X-MBX-APIKEY': self.api_key
            }           

            params = self.get_signature(params)
            async with session.post(self.create_order_url, headers=headers, params=params) as response:
                return await self.requests_logger(response, self.user_label, strategy_name, "place_order", symbol, position_side)
            
        except Exception as ex:
            self.info_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name} at line {inspect.currentframe().f_lineno}")

        return {}, self.user_label, strategy_name, symbol, position_side      

    async def place_risk_order(
            self,
            session: aiohttp.ClientSession,
            strategy_name: str,
            symbol: str,
            qty: float,
            side: str,
            position_side: str,
            target_price: float,
            suffix: str,
            order_type: str # MASRKET | LIMIT
        ):
        """
        Универсальный метод для установки условных ордеров (SL/TP/LIMIT) на Binance Futures.

        :param suffix: 
            'sl'  — стоп-лосс
            'tp'  — тейк-профит
        """
        try:
            if suffix == "sl":
                params = {
                    "symbol": symbol,
                    "side": side,
                    "type": "STOP_MARKET",
                    "quantity": abs(qty),
                    "positionSide": position_side,
                    "stopPrice": target_price,
                    "closePosition": "true",
                    "recvWindow": 20000,
                    "newOrderRespType": "RESULT"
                }

            elif suffix == "tp": 
                if order_type.upper() == "MARKET":       
                    params = {
                        "symbol": symbol,
                        "side": side,
                        "type": "TAKE_PROFIT_MARKET",
                        "quantity": abs(qty),
                        "positionSide": position_side,
                        "stopPrice": target_price,
                        "closePosition": "true",
                        "recvWindow": 20000,
                        "newOrderRespType": "RESULT"
                    }

                elif order_type.upper() == "LIMIT":                
                    params = {
                        "symbol": symbol,
                        "side": side,
                        "type": "LIMIT",
                        "quantity": abs(qty),
                        "positionSide": position_side,
                        "price": str(target_price),  # лимитная цена
                        "timeInForce": "GTC",       # удерживать пока не исполнится
                        "recvWindow": 20000,
                        "newOrderRespType": "RESULT"
                    }

                else:
                    raise ValueError(f"Неизвестный suffix: {suffix}")

            headers = {"X-MBX-APIKEY": self.api_key}
            params = self.get_signature(params)

            async with session.post(
                self.create_order_url,
                headers=headers,
                params=params
            ) as response:
                return await self.requests_logger(
                    response,
                    self.user_label,
                    strategy_name,
                    f"place_{suffix.lower()}_order",
                    symbol,
                    position_side
                )

        except Exception as ex:
            self.info_handler.debug_error_notes(
                f"{ex} in {inspect.currentframe().f_code.co_name} "
                f"at line {inspect.currentframe().f_lineno}"
            )

        return {}, self.user_label, strategy_name, symbol, position_side    
        
    async def cancel_order_by_id(
            self,
            session: aiohttp.ClientSession,
            strategy_name: str,
            symbol: str,
            order_id: str,
            suffix: str
        ):
        """
        Универсальный метод отмены ордера по order_id (SL или TP).
        Параметр `suffix`: 'SL' или 'TP'
        """
        try:
            params = {
                "symbol": symbol,
                "orderId": order_id,
                "recvWindow": 20000
            }
            headers = {
                'X-MBX-APIKEY': self.api_key
            }

            params = self.get_signature(params)
            async with session.delete(self.cancel_order_url, headers=headers, params=params) as response:
                return await self.requests_logger(response, self.user_label, strategy_name, f"cancel_{suffix.lower()}_order", symbol, order_id)

        except Exception as ex:
            self.info_handler.debug_error_notes(f"{ex} in {inspect.currentframe().f_code.co_name} at line {inspect.currentframe().f_lineno}")

        return {}, self.user_label, strategy_name, symbol, order_id