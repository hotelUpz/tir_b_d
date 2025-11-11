# utils.py

import asyncio
import aiofiles
from pathlib import Path
from collections import OrderedDict
import pickle
from itertools import islice
from typing import *
import json
from datetime import datetime
from c_log import  TIME_ZONE
from decimal import Decimal, getcontext
from c_log import ErrorHandler
import os


getcontext().prec = 28  # точность Decimal

PRECISION = 28

def get_proxy_list(cfg_list: List) -> Optional[str]:
    """Возвращает URL первого активного прокси из cfg_list."""
    proxy_set = set()
    for cfg in cfg_list:
        if cfg and cfg.get("enable"):
            login = cfg.get("proxy_login")
            password = cfg.get("proxy_password")
            host = cfg.get("proxy_address")
            port = cfg.get("proxy_port")
            proxy_set.add(f"http://{login}:{password}@{host}:{port}")
        else:
            proxy_set.add(None)

    return list(proxy_set)

def chunk_list(iterable, n):
    # Для детерминизма: если пришёл set — отсортируем
    if isinstance(iterable, set):
        iterable = sorted(iterable)
    it = iter(iterable)
    while True:
        chunk = list(islice(it, n))
        if not chunk:
            break
        yield chunk


def save_to_json(data, filename="data.json"):
    """
    Сохраняет словарь/список в JSON-файл с отступами.

    :param data: dict или list – данные для сохранения
    :param filename: str – путь до файла (например, '/home/user/data.json')
    """
    try:
        # Убедимся, что директория существует
        # os.makedirs(os.path.dirname(filename), exist_ok=False)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # print(f"Файл сохранён: {filename}")
    except Exception as e:
        print(f"Ошибка при сохранении: {e}")

# //

def qty_calc(
    margin_size: float,
    entry_price: float,
    leverage: float,
    volume_rate: float,
    precision: int,
    debug_label: str
) -> Optional[float]:
    """
    Рассчитывает количество (quantity) для сделки.
    """
    if any(not isinstance(x, (int, float)) or x <= 0 for x in [margin_size, entry_price, leverage]):
        print(f"{debug_label}: Invalid input parameters in size_calc")
        return None

    try:
        deal_amount = margin_size * volume_rate / 100
        raw_qty = (deal_amount * leverage) / entry_price
        qty = round(raw_qty, precision)

        # # === DEBUGGING METRICS (можно закомментировать при необходимости) ===
        # print(f"{debug_label}: margin_size = {margin_size}")
        # print(f"{debug_label}: volume_rate = {volume_rate}")
        # print(f"{debug_label}: deal_amount = margin_size * volume_rate = {deal_amount}")
        # print(f"{debug_label}: leverage = {leverage}")
        # print(f"{debug_label}: entry_price = {entry_price}")
        # print(f"{debug_label}: raw_qty = (deal_amount * leverage) / entry_price = {raw_qty}")
        # print(f"{debug_label}: precision = {precision}")
        # print(f"{debug_label}: final qty = {qty}")
        # # ====================================================================

        return qty
    except Exception as e:
        print(f"{debug_label}: Error in size_calc: {e}")
        return None

def has_open_position(response, symbol: str, side: str) -> Optional[bool]:
    """Возвращает True/False/None"""
    try:           
        if not response or not response.get("success"):
            return None

        for pos in response["positions"]:
            if pos["symbol"] == symbol and pos["side"] == side.upper():
                if float(pos["volume"]) > 0:
                    return True
        return False
    except Exception:
        return None

# ////

def milliseconds_to_datetime(milliseconds):
    if milliseconds is None:
        return "N/A"
    try:
        ms = int(milliseconds)   # <-- приведение к int
        if milliseconds < 0: return "N/A"
    except (ValueError, TypeError):
        return "N/A"

    if ms > 1e10:  # похоже на миллисекунды
        seconds = ms / 1000
    else:
        seconds = ms

    dt = datetime.fromtimestamp(seconds, TIME_ZONE)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def to_human_digit(value):
    if value is None:
        return "N/A"
    getcontext().prec = PRECISION
    dec_value = Decimal(str(value)).normalize()
    if dec_value == dec_value.to_integral():
        return format(dec_value, 'f')
    else:
        return format(dec_value, 'f').rstrip('0').rstrip('.') 

def format_duration(ms: int) -> str:
    """
    Конвертирует миллисекундную разницу в формат "Xh Ym" или "Xm" или "Xs".
    :param ms: длительность в миллисекундах
    """
    if ms is None:
        return ""
    
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0 and minutes > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0 and seconds > 0:
        return f"{minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return f"{seconds}s"
    
def format_msg(
    cfg: dict,
    indent: int = 0,
    target_key: str = None,
    alt_key: str = None,
    ex_key: str = None,
) -> str:
    lines = []
    pad = "  " * indent

    for k, v in cfg.items():
        # исключаем ключ
        if k == ex_key:
            continue

        # заменяем имя ключа
        display_key = alt_key if k == target_key else k

        if isinstance(v, dict):
            lines.append(f"{pad}• {display_key}:")
            lines.append(format_msg(v, indent + 1, target_key, alt_key, ex_key))
        else:
            lines.append(f"{pad}• {display_key}: {v}")

    return "\n".join(lines)


# ============================================================
#  ПРОСТЫЕ ЛОКАЛЬНЫЕ ПУТИ (всегда относительно текущего запуска)
# ============================================================

DEBUG_DIR  = Path("INFO/DEBUG")
TRADES_DIR = Path("INFO/TRADES")

DEBUG_ERR_FILE        = DEBUG_DIR  / "error_.txt"
DEBUG_INFO_FILE       = DEBUG_DIR  / "info_.txt"
TRADES_INFO_FILE      = TRADES_DIR / "info_.txt"
TRADES_SECONDARY_FILE = TRADES_DIR / "secondary_.txt"
TRADES_FAILED_FILE    = TRADES_DIR / "failed_.txt"
TRADES_SUCC_FILE      = TRADES_DIR / "success_.txt"

        
# ///        
class FileManager:
    def __init__(self, info_handler: ErrorHandler):   
        info_handler.wrap_foreign_methods(self)
        self.info_handler = info_handler

    async def cache_exists(self, file_name="pos_cache.pkl"):
        """Проверяет, существует ли файл и не пустой ли он."""
        return await asyncio.to_thread(lambda: os.path.isfile(file_name) and os.path.getsize(file_name) > 0)

    async def load_cache(self, file_name="pos_cache.pkl"):
        """Читает данные из pickle-файла."""
        def _load():
            with open(file_name, "rb") as file:
                return pickle.load(file)
        try:
            return await asyncio.to_thread(_load)
        except (FileNotFoundError, EOFError):
            return {}
        except Exception as e:
            self.info_handler.debug_error_notes(f"Unexpected error while reading {file_name}: {e}")
            return {}        

    def _write_pickle(self, data, file_name):
        with open(file_name, "wb") as file:
            pickle.dump(data, file, protocol=pickle.HIGHEST_PROTOCOL)

    async def write_cache(self, data_dict, file_name="pos_cache.pkl"):
        """Сохраняет данные в pickle-файл."""
        try:
            await asyncio.to_thread(self._write_pickle, data_dict, file_name)
        except Exception as e:
            self.info_handler.debug_error_notes(f"Error while caching data: {e}")


class WriteLogManager(FileManager):
    """Управляет асинхронной записью логов в файлы и очисткой списков логов."""

    def __init__(self, info_handler: ErrorHandler, max_log_lines: int = 250) -> None:
        super().__init__(info_handler)
        self.MAX_LOG_LINES: int = max_log_lines

    async def write_logs(self) -> None:

        logs: List[Tuple[List[str], Path]] = [
            (self.info_handler.debug_err_list, DEBUG_ERR_FILE),
            (self.info_handler.debug_info_list, DEBUG_INFO_FILE),
            (self.info_handler.trade_info_list, TRADES_INFO_FILE),
            (self.info_handler.trade_failed_list, TRADES_FAILED_FILE),
            (self.info_handler.trade_succ_list, TRADES_SUCC_FILE),
        ]

        if not any(log_list for log_list, _ in logs):
            return

        for log_list, file_path in logs:
            # print(log_list)
            # print(f"[LOG DEBUG] Writing logs to {file_path}")
            if not log_list:
                continue

            file_path.parent.mkdir(parents=True, exist_ok=True)  # Создаёт директорию, если не существует

            existing_lines: List[str] = []
            if file_path.exists():
                async with aiofiles.open(str(file_path), "r", encoding="utf-8") as f:
                    existing_lines = await f.readlines()

            new_lines = [f"{log}\n" for log in log_list]
            total_lines = existing_lines + new_lines
            total_lines = list(OrderedDict.fromkeys(total_lines))

            if len(total_lines) > self.MAX_LOG_LINES:
                total_lines = total_lines[-self.MAX_LOG_LINES:]

            async with aiofiles.open(str(file_path), "w", encoding="utf-8") as f:
                await f.writelines(total_lines)

            log_list.clear()

        self.info_handler.trade_secondary_list.clear()