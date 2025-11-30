# networks.py

import asyncio
import aiohttp
from typing import *
from c_log import ErrorHandler

CHECK_URL = "https://api.binance.com/api/v3/ping"
SESSION_CHECK_INTERVAL = 15  # секунд


class NetworkManager:
    def __init__(self, info_handler: ErrorHandler, proxy_list: Optional[List[Optional[str]]] = None,
                 user_label: Optional[str] = None, stop_bot: bool = False):
        info_handler.wrap_foreign_methods(self)
        self.info_handler = info_handler

        self.proxy_list: List[Optional[str]] = proxy_list or [None]
        self.proxy_index: int = 0
        self.proxy_url: Optional[str] = self.proxy_list[self.proxy_index]

        self.user_label = user_label or "network"
        self.session: Optional[aiohttp.ClientSession] = None
        self._ping_task: Optional[asyncio.Task] = None
        self.stop_bot = stop_bot

    # ============================================================
    #  СЕССИЯ
    # ============================================================
    async def initialize_session(self):
        """Создает новую aiohttp-сессию, проксируя через текущий proxy_url."""
        if self.session and not self.session.closed:
            return

        try:
            if self.proxy_url:
                connector = aiohttp.TCPConnector(ssl=False)
                self.session = aiohttp.ClientSession(
                    connector=connector,
                    trust_env=False,
                    proxy=self.proxy_url
                )
                self.info_handler.debug_error_notes(
                    f"{self.user_label}: создана новая сессия с прокси {self.proxy_url}")
            else:
                self.session = aiohttp.ClientSession()
                self.info_handler.debug_error_notes(
                    f"{self.user_label}: создана новая сессия без прокси")
        except Exception as e:
            self.info_handler.debug_error_notes(
                f"{self.user_label}: ошибка при создании сессии: {e}"
            )

    async def _check_session_connection(self, session: aiohttp.ClientSession) -> tuple[bool, Optional[int]]:
        """
        Проверяет доступность Binance API через текущую сессию.
        Возвращает (ok, status_code | None).
        """
        try:
            async with session.get(CHECK_URL, timeout=8) as response:
                ok = (response.status == 200)
                if not ok:
                    # тут явный лог по не-200 статусу
                    self.info_handler.debug_error_notes(
                        f"{self.user_label}: неуспешный HTTP статус → {response.status}"
                    )
                return ok, response.status

        except Exception as e:
            self.info_handler.debug_error_notes(
                f"{self.user_label}: ошибка соединения → {type(e).__name__}: {e}"
            )
            return False, None

    async def _switch_to_next_proxy(self):
        """Переключает на следующий прокси из списка."""
        self.proxy_index = (self.proxy_index + 1) % len(self.proxy_list)
        self.proxy_url = self.proxy_list[self.proxy_index]
        self.info_handler.debug_error_notes(
            f"{self.user_label}: смена прокси → {self.proxy_url or 'без прокси'}"
        )

    # ============================================================
    #  ПРОВЕРКА И ВОССТАНОВЛЕНИЕ
    # ============================================================
    async def validate_session(self) -> tuple[bool, bool, Optional[int]]:
        """
        Проверяет соединение и восстанавливает при необходимости.
        Возвращает (ok, was_reconnected, last_status).
        - ok: True, если удалось получить 200
        - was_reconnected: был ли переход на другие прокси
        - last_status: последний HTTP статус или None при сетевой ошибке
        """
        was_reconnected = False
        last_status: Optional[int] = None

        for attempt in range(1, len(self.proxy_list) * 2):  # 2 прохода по списку
            await self.initialize_session()

            ok, status = await self._check_session_connection(self.session)
            last_status = status

            if ok:
                return True, was_reconnected, last_status

            # закрываем перед пересозданием
            try:
                await self.session.close()
            except Exception:
                pass

            await self._switch_to_next_proxy()
            await asyncio.sleep(min(3 + attempt, 15))
            was_reconnected = True
            self.info_handler.debug_error_notes(
                f"{self.user_label}: попытка переподключения #{attempt}"
            )

        self.info_handler.debug_error_notes(
            f"❌ {self.user_label}: не удалось восстановить соединение после всех прокси", True
        )
        return False, was_reconnected, last_status

    # ============================================================
    #  ФОНОВАЯ ПРОВЕРКА / ПИНГ
    # ============================================================
    async def ping_session(self):
        """
        Поддерживает "живую" сессию, проверяя каждые SESSION_CHECK_INTERVAL секунд.
        При сбое пересоздает сессию.
        """
        while not self.stop_bot:
            ok, reconnected, status = await self.validate_session()
            if not ok:
                self.info_handler.debug_error_notes(
                    f"{self.user_label}: ping неудачен — сессия мертва (status={status})"
                )
            elif reconnected:
                self.info_handler.debug_error_notes(
                    f"{self.user_label}: сессия была пересоздана, status={status}"
                )
            # else:
            #     self.info_handler.debug_error_notes(
            #         f"{self.user_label}: ping OK, status={status}"
            #     )
            await asyncio.sleep(SESSION_CHECK_INTERVAL)

    async def start_ping_loop(self):
        """Запускает фонового пингера."""
        if not self._ping_task or self._ping_task.done():
            self._ping_task = asyncio.create_task(self.ping_session())
            self.info_handler.debug_error_notes(
                f"{self.user_label}: запущен фоновой ping-сервис"
            )

    async def shutdown_session(self):
        """Закрывает aiohttp-сессию и останавливает пинг-задачу."""
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        if self.session and not self.session.closed:
            try:
                await self.session.close()
                self.info_handler.debug_error_notes(
                    f"{self.user_label}: aiohttp-сессия закрыта"
                )
            except Exception as e:
                self.info_handler.debug_error_notes(
                    f"{self.user_label}: ошибка при закрытии сессии: {e}"
                )

