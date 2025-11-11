# main.py

import asyncio
import aiohttp
import time
# from pprint import pprint
from typing import *
from a_config import *
from c_log import ErrorHandler
from c_network import NetworkManager
from c_utils import get_proxy_list, qty_calc, WriteLogManager, has_open_position
from c_validators import OrderValidator
from API.BINANCE.client import BinancePublicApi, BinancePrivateApi
from API.TG.tg_notifier import TelegramNotifier, Formatter
from d_signal import FairSignalDetector, TrendConfirmSignal
import traceback


MAIN_FREQUENTCY: float = 1 # sec


class Core:
    def __init__(self):
        self.info_handler = ErrorHandler()

        proxy_list = get_proxy_list(cfg_list=PROXY_LIST)

        self.stop_bot: bool = False

        self.public_connector = NetworkManager(
            info_handler=self.info_handler,
            proxy_list=proxy_list,
            user_label="[PUBLIC]",
            stop_bot=self.stop_bot
        )

        self.binance_public = BinancePublicApi(info_handler=self.info_handler)

        self.binance_private = BinancePrivateApi(
            info_handler=self.info_handler,
            api_key=BINANCE_API_PUBLIC_KEY,
            api_secret=BINANCE_API_PRIVATE_KEY,
            user_label=USER_NAME
        )

        self.order_validator = OrderValidator(info_handler=self.info_handler)

        self.signal_detector = FairSignalDetector()
        self.signal_confirm = TrendConfirmSignal()

        self.write_log = WriteLogManager(info_handler=self.info_handler, max_log_lines=MAX_LOG_LINES)

        self.notifier = TelegramNotifier(
            token=TG_BOT_TOKEN,
            chat_ids=[CHAT_ID_1],
            info_handler=self.info_handler,
            stop_bot=self.stop_bot
        )

        self.margin_type = "ISOLATED" if MARGIN_MODE == 1 else "CROSSED"
        self.risk_order_type = "LIMIT" if TP_TYPE == 1 else "MARKET"
        self.secondary_cache = set()

        self.position_vars: dict = {}
        self.pos_vars_lock = asyncio.Lock()  

        self.symbols_state_event = asyncio.Event()

        self.info_handler.wrap_foreign_methods(self)

    async def cancel_order_template(
        self,
        session,
        strategy_name: str,
        symbol:        str,
        suffix:        str = "tp"
    ) -> bool:
        debug_label = f"[{USER_NAME}][{STRATEGY_NAME}][{symbol}][LONG]"
        async with self.pos_vars_lock:
            order_id = self.position_vars.get(symbol, {}).get(f"{suffix.upper()}_order_id")

        if not order_id:
            # self.info_handler.trades_info_notes(
            #     f"[INFO]{debug_label}[{suffix.upper()}]: отсутствует ID ордера.", False
            # )
            return True  # Считаем успешным, так как отменять нечего

        response = await self.binance_private.cancel_order_by_id(
            session=session,
            strategy_name=strategy_name,
            symbol=symbol,
            order_id=order_id,
            suffix=suffix
        )

        if self.order_validator.validate_cancel_risk_response(response, suffix, debug_label):
            async with self.pos_vars_lock:
                self.position_vars[symbol] = {"in_position": False, "tp_order_id": None}

            return True
        
        return False

    async def _place_take_profit(
            self,
            session,
            symbol: str,
            qty: float,
            price_precision: int,
            executed_price: float,
            debug_label: str
        ) -> bool:
        """Ставит TP ордер и сохраняет ID."""

        target_price = round(executed_price * (1 + TP / 100), price_precision)
        try:
            response = await self.binance_private.place_risk_order(
                session=session,
                strategy_name=STRATEGY_NAME,
                symbol=symbol,
                qty=qty,
                side="SELL",
                position_side="LONG",
                target_price=target_price,
                suffix="tp",
                order_type=self.risk_order_type
            )
        except Exception as e:
            self.info_handler.debug_info_notes(f"[CRITICAL][{debug_label}] Ошибка при установке TP: {e}")
            return False

        risk_details = self.order_validator.validate_risk_response(response, "TP", debug_label)
        self.info_handler.debug_info_notes(f"[INFO][{debug_label}] TP validation result: {risk_details}")
        if not risk_details:
            return False

        ok_risk, order_id = risk_details
        if ok_risk:
            async with self.pos_vars_lock:
                self.position_vars[symbol]["tp_order_id"] = order_id
            self.info_handler.debug_info_notes(f"[INFO][{debug_label}] TP order placed: order_id={order_id}")
            return True
        return False

    async def _place_order(
            self,
            session,
            symbol: str,
            qty: float,
            leverage: int,
            debug_label: str
        ) -> Optional[float]:
        """Устанавливает плечо, режим маржи и открывает MARKET ордер."""

        if symbol not in self.secondary_cache:
            self.secondary_cache.add(symbol)
            await self.binance_private.set_margin_type(
                session=session,
                strategy_name=STRATEGY_NAME,
                symbol=symbol,
                margin_type=self.margin_type
            )
            await self.binance_private.set_leverage(
                session=session,
                strategy_name=STRATEGY_NAME,
                symbol=symbol,
                lev_size=leverage
            )

        order_start_time = time.monotonic()
        market_order_result = await self.binance_private.make_order(
            session=session,
            strategy_name=STRATEGY_NAME,
            symbol=symbol,
            qty=qty,
            side="BUY",
            position_side="LONG",
            market_type="MARKET"
        )
        self.info_handler.debug_info_notes(
            f"[INFO][{debug_label}] Make order in {time.monotonic() - order_start_time:.2f}s"
        )

        ok, order_details = self.order_validator.validate_market_response(market_order_result[0], debug_label)
        executed_price = order_details.get("price")

        if not ok or not executed_price:
            self.info_handler.debug_info_notes(f"[CRITICAL][{debug_label}] Не удалось открыть ордер.")
            return None

        async with self.pos_vars_lock:
            self.position_vars[symbol]["in_position"] = True

        print(f"✅ Открыт ордер {symbol} по цене {executed_price}")
        return executed_price

    async def _prepare_order_data(
            self,
            session,
            symbol: str,
            cur_price: float,
            debug_label: str,
            debug: bool
        ) -> Optional[tuple]:
        """Проверяет фильтры, расчёт маржи и количества."""

        prec = self.binance_public.get_precisions(symbol)
        if not prec:
            self.info_handler.debug_error_notes(f"[{debug_label}] Нет данных по фильтрам {symbol}")
            return None
        qty_precision, price_precision = prec

        trade_spec = self.binance_private.leverage_brackets.get(symbol)
        if not trade_spec:
            self.info_handler.debug_error_notes(f"[{debug_label}] Нет leverage_brackets для {symbol}")
            return None
        max_leverage = trade_spec.get("max_leverage")
        max_notional_value = trade_spec.get("max_notional")

        if debug:
            print(
                f"[PRECISIONS]\n"
                f"  Qty precision:   {qty_precision}\n"
                f"  Price precision: {price_precision}\n"
                f"  Max leverage:    {max_leverage}\n"
                f"  Max notional:    {max_notional_value}"
            )

        leverage = FORCE_LEVERAGE or max_leverage

        # === выбор маржи ===
        if FORCE_MARGIN:
            plane_size = FORCE_MARGIN * leverage
        else:
            allowed_by_notional = max_notional_value * SIZE_FACTOR / 100
            allowed_by_margin = (MARGIN_LIMIT * leverage) if MARGIN_LIMIT else float("inf")
            plane_size = min(allowed_by_notional, allowed_by_margin)

        # === баланс ===
        required_usdt = plane_size / leverage + MARGIN_BUFER
        available_usdt = await self.binance_private.get_avi_balance(session=session)
        margin_size = min(available_usdt, required_usdt)

        async with self.pos_vars_lock:
            self.position_vars.setdefault(symbol, {"in_position": False, "tp_order_id": None})

        qty = qty_calc(
            margin_size=margin_size,
            entry_price=cur_price,
            leverage=leverage,
            volume_rate=100,
            precision=qty_precision,
            debug_label=debug_label
        )

        if not qty:
            self.info_handler.debug_info_notes(f"[CRITICAL][{debug_label}] Ошибка при расчете количества.")
            return None

        return qty, price_precision, leverage

    async def set_order_template(
            self,
            session: aiohttp.ClientSession,
            symbol: str,
            cur_price: float,
            debug: bool = True
        ) -> Optional[bool]:

        debug_label = f"[{USER_NAME}][{STRATEGY_NAME}][{symbol}][LONG]"

        # === 1️⃣ подготовка параметров ===
        prep = await self._prepare_order_data(session, symbol, cur_price, debug_label, debug)
        if not prep:
            return False
        qty, price_precision, leverage = prep

        # === 2️⃣ установка ордера ===
        executed_price = await self._place_order(session, symbol, qty, leverage, debug_label)
        if not executed_price:
            return False

        # === 3️⃣ установка TP ===
        success = await self._place_take_profit(session, symbol, qty, price_precision, executed_price, debug_label)
        return success

    async def symbols_state_updater(self, session):
        while not self.stop_bot:
            try:
                await self.binance_public.update_filtered_symbols(session)
                # await asyncio.sleep(0)
                await self.binance_private.update_leverage_brackets(session)
            finally:
                self.symbols_state_event.set()
                await asyncio.sleep(SYMBOLS_FREQUENCY)

    async def update_positions(self):
        """Обновляет статусы позиций и очищает кеш по закрытым символам."""
        open_positions = await self.binance_private.get_open_positions(session=self.public_session)
        # возвращает актуальные позиции пользователя

        for symbol in list(self.position_vars.keys()):
            in_position = has_open_position(open_positions, symbol, "LONG")

            if in_position:
                # позиция есть → просто помечаем активной
                async with self.pos_vars_lock:
                    self.position_vars[symbol]["in_position"] = True
                continue

            # если позиции больше нет → отменяем TP и очищаем кеш
            await self.cancel_order_template(
                session=self.public_session,
                strategy_name=STRATEGY_NAME,
                symbol=symbol,
                suffix="tp"
            )

            async with self.pos_vars_lock:
                self.position_vars[symbol]["in_position"] = False
                # удаляем старые сигналы
                if symbol in self.signal_detector.signals_cache:
                    del self.signal_detector.signals_cache[symbol]
                self.signal_detector.signal_symbols.discard(symbol)

        # self.info_handler.debug_info_notes(f"[POS UPDATE] ✅ Обновление позиций завершено ({len(open_positions)} активных)")

    async def process_signals(self):
        all_hot  = await self.binance_public.get_all_hot_prices(self.public_session)
        all_fair = await self.binance_public.get_all_fair_prices(self.public_session)
        if not all_hot or not all_fair:
            self.info_handler.debug_info_notes("❌ Ошибка получения цен.")
            return

        signal = await self.signal_detector.check(all_hot, all_fair, self.position_vars, self.pos_vars_lock)
        if not signal:
            return

        pos_limit_flag = (
            POSITION_LIMIT is not None
            and sum(
                1 for x in (self.position_vars or {}).values()
                if isinstance(x, dict) and x.get("in_position", False)
            ) >= POSITION_LIMIT
        )
        if pos_limit_flag:
            # print("Сработал ограничитель числа позиций")
            return

        signal_symbol, diff_percent = signal
        clines = await self.binance_public.get_klines_basic(
            session=self.public_session,
            symbol=signal_symbol,
            interval=self.signal_confirm.tf,
            limit=int(self.signal_confirm.slow * 2.5),
        )
        trend = self.signal_confirm.detect_trend(clines)
        if trend not in (None, "UP"):
            self.info_handler.debug_info_notes(f"📈 Тренд НЕ подтверждён для {signal_symbol}. Пропускаем сигнал.")
            return

        open_positions = await self.binance_private.get_open_positions(session=self.public_session)
        if has_open_position(open_positions, signal_symbol, "LONG"):
            print(f"Сигнал не обрабатываем. Монета {signal_symbol} уже в позиции")
            return

        msg = "📈 Тренд подтверждён." if TREND_LINE.get(self.signal_confirm.tf, {}).get("enable") \
            else "📈 Подтверждение тренда не требуется."
        self.info_handler.debug_info_notes(f"Сигнал по монете {signal_symbol}. {msg}")

        last_price = all_hot.get(signal_symbol)
        fair_price = all_fair.get(signal_symbol)
        precisions = self.binance_public.get_precisions(signal_symbol)
        price_precision = precisions[1] if precisions else 2

        signal_data = {
            "symbol": signal_symbol,
            "last_price": last_price,
            "fair_price": fair_price,
            "diff_percent": round(diff_percent, 2),
            "price_precision": price_precision
        }
        report_text = Formatter.format_coins_for_tg(signal_data) or ""
        asyncio.create_task(self.notifier.send(text=report_text))

        await self.set_order_template(session=self.public_session, symbol=signal_symbol, cur_price=last_price)

    async def _run(self):
        self.info_handler.debug_info_notes("[INFO] ✨ Бот начал работу.")

        ok, _ = await self.public_connector.validate_session()
        if not ok:
            raise RuntimeError("Failed to initialize session for 'public'")

        await self.public_connector.start_ping_loop()
        self.public_session: aiohttp.ClientSession = self.public_connector.session

        await self.binance_private.set_hedge_mode(self.public_session)
        await asyncio.sleep(0.1)

        asyncio.create_task(self.symbols_state_updater(self.public_session))        
        try:
            await asyncio.wait_for(self.symbols_state_event.wait(), timeout=30.0)
            self.info_handler.debug_info_notes("Leverage brackets и символы загружены")
        except asyncio.TimeoutError:
            self.info_handler.debug_info_notes("Таймаут загрузки brackets — продолжаем (обновятся в фоне)")

        # === таймеры ===
        signal_updating_time     = time.monotonic()
        status_pos_updating_time = time.monotonic()
        last_write_logs_time     = time.monotonic()
        first_pos_update         = True

        while not self.stop_bot:
            try:
                now = time.monotonic()

                # ======================================================
                # 1️⃣ блок обработки сигналов
                # ======================================================
                if now - signal_updating_time >= SIGNAL_FREQUENCY:
                    signal_updating_time = now
                    try:
                        await self.process_signals()
                    except Exception as e:
                        self.info_handler.debug_error_notes(f"[SIGNAL] Ошибка: {e}")

                # ======================================================
                # 2️⃣ блок обновления позиций
                # ======================================================
                if now - status_pos_updating_time >= UPDATE_POSITION_FREQUENCY or first_pos_update:
                    status_pos_updating_time = now
                    first_pos_update = False
                    try:
                        await self.update_positions()
                    except Exception as e:
                        self.info_handler.debug_error_notes(f"[POS UPDATE] Ошибка: {e}")

                # ======================================================
                # 3️⃣ блок записи логов
                # ======================================================
                if WRITE_TO_LOG and (now - last_write_logs_time >= WRITE_LOGS_INTERVAL):
                    last_write_logs_time = now
                    try:
                        await self.write_log.write_logs()
                    except Exception as e:
                        self.info_handler.debug_error_notes(f"[LOG] Ошибка при записи логов: {e}")

            except Exception as ex:
                tb = traceback.format_exc()
                self.info_handler.debug_error_notes(f"[_run.main.py] Ошибка в основном цикле: {ex}\n{tb}", is_print=True)

            await asyncio.sleep(MAIN_FREQUENTCY)


async def main():
    instance = Core()
    try:
        await instance._run()
    except asyncio.CancelledError:
        print("🚩 Асинхронная задача была отменена.")
    except KeyboardInterrupt:
        print("\n⛔ Остановка по Ctrl+C")
    # except Exception as e:
    #     print(f"\n❌ Ошибка: {type(e).__name__} — {e}")
    finally:
        instance.stop_bot = True
        await instance.public_connector.shutdown_session()  # ← добавь это
        print("Сессии закрываются...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

# -- лечим хром
# google-chrome-stable --enable-features=UseOzonePlatform --ozone-platform=wayland


# # убедились, что права уже установлены (вы это сделали)
# chmod 600 ssh_key

# # запустить агент (если он не запущен) и добавить ключ из текущей директории
# eval "$(ssh-agent -s)" && ssh-add ./ssh_key

# ssh-add -l        # выведет список добавленных ключей или "The agent has no identities"

# ssh -T git@github.com