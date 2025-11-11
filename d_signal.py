# sigmal.py

import asyncio
import time
# import numpy as np
import pandas_ta as ta
import pandas as pd
from typing import *
from a_config import DIFF_PCT, SIGNAL_TTL, TREND_LINE, BLACK_SET


class FairSignalDetector:
    """
    Отслеживает расхождение справедливой и горячей цены с подтверждением по времени удержания сигнала.
    fair_price > last_price и разница >= DIFF_PCT.
    """

    def __init__(self):
        self.signals_cache: Dict[str, Dict[str, float]] = {}  # {symbol: {"first_time": float}}
        self.signal_symbols: Set[str] = set()
        self.diff_pct = abs(DIFF_PCT) if DIFF_PCT else 5.0
        self.ttl = SIGNAL_TTL or 60

    async def check(
        self,
        all_hot: Dict[str, float],
        all_fair: Dict[str, float],
        position_vars: Dict[str, Dict[str, Any]],
        pos_vars_lock: asyncio.Lock
    ) -> Optional[str]:
        """
        Проверяет все символы и возвращает первый подтвержденный сигнал (symbol).
        Возвращает None, если ничего не подтверждено.
        """
        if not all_hot or not all_fair:
            return None

        now = time.time()

        for symbol, last_price in all_hot.items():
            if symbol in BLACK_SET:
                continue

            if symbol in self.signal_symbols:
                continue

            fair_price = all_fair.get(symbol)
            if last_price is None or fair_price is None:
                continue

            diff_percent = (fair_price - last_price) / last_price * 100

            was_in_position = bool(symbol in position_vars)

            # --- основное условие ---
            if diff_percent >= self.diff_pct:  # fair > last уже заложено в diff
                record = self.signals_cache.get(symbol)

                # первый фикс
                if not record:
                    self.signals_cache[symbol] = {"first_time": now}
                    continue

                # подтверждение по TTL
                if was_in_position or now - record["first_time"] >= self.ttl:
                    del self.signals_cache[symbol]
                    self.signal_symbols.add(symbol)
                    return symbol, diff_percent

            else:
                # условие не удерживается — сброс таймера
                if symbol in self.signals_cache:
                    self.signals_cache[symbol]["first_time"] = now
                    async with pos_vars_lock:
                        if symbol in position_vars:
                            del position_vars[symbol]

        return None


# ============================================================
#  ПОДТВЕРЖДАЮЩИЙ СИГНАЛ: анализ тренда по линиям
# ============================================================

class TrendConfirmSignal:
    """
    Проверяет направление тренда по короткой и длинной EMA через pandas_ta.
    Восходящий тренд, если EMA(fast) > EMA(slow).
    Если индикатор отключён — тренд считается восходящим ("UP").
    """

    def __init__(self, trend_config: dict = None):
        self.trend_cfg = trend_config or TREND_LINE
        self.tf = next(iter(self.trend_cfg.keys()), "5m")

        cfg = self.trend_cfg.get(self.tf, {})
        self.enabled = cfg.get("enable", False)
        self.fast = cfg.get("fast", 5)
        self.slow = cfg.get("slow", 10)

    def detect_trend(self, df: pd.DataFrame) -> Optional[str]:
        """
        Принимает DataFrame со столбцом 'Close'.
        Возвращает 'UP' | 'DOWN' | None.
        """
        if not self.enabled:
            return "UP"

        if df.empty or 'Close' not in df.columns:
            return None

        if len(df) < self.slow:
            return None

        df = df.copy()
        df['ema_fast'] = ta.ema(df['Close'], length=self.fast)
        df['ema_slow'] = ta.ema(df['Close'], length=self.slow)

        last_row = df.iloc[-1]
        fast_val, slow_val = last_row['ema_fast'], last_row['ema_slow']
        # print(fast_val, slow_val)

        if pd.isna(fast_val) or pd.isna(slow_val):
            return None

        if fast_val > slow_val:
            return "UP"
        elif fast_val <= slow_val:
            return "DOWN"
        return None