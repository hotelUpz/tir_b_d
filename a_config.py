# config.py

from typing import *

# CORE
USER_NAME:      str   = "Nik"     # имя клиента
STRATEGY_NAME:  str   = "Tir"     # лейба стратегии
SIZE_FACTOR:    float = 99        # % от максимумально допустимого номинала позиции
FORCE_MARGIN:   float = 1         # $ задаем свою мпржу | None - откл
MARGIN_LIMIT:   float = 2         # $ максимально допустимая маржа на сделку
MARGIN_MODE:    int   = 2         # 1 -- ISOLATED, 2 -- CROSSED
MARGIN_BUFER:   float = 0.0       # $ запас маржи, чтобы хватило на сделку
FORCE_LEVERAGE: int   = None      # форсированное плечо. Если не None то берем максимальное из доступного
TP:             float = 1         # take profit %
TP_TYPE:        int   = 1         # 1 -- limit type, 2 -- market type
BLACK_SET:      set   = {"BRUSDT", "ARIAUSDT", "REIUSDT", "SOPHUSDT"}     # черный список монет. Формат монеты: "BTCUSDT" и т.д.
POSITION_LIMIT: int   = 1         # ограничитель одновременно открытых позиций | None - без ограничения


# SYSTEM
SYMBOLS_FREQUENCY:         float = 60    # частота обновления данных по символам. В секундах
SIGNAL_FREQUENCY:          float = 2     # частота парсинга сигнала. В секундах
UPDATE_POSITION_FREQUENCY: float = 3     # частота обновления статуса позиций. В секундах
WRITE_LOGS_INTERVAL:       float = 1     # частота записей логов
MAX_LOG_LINES:             int   = 1000  # количество строк в лог файлах
WRITE_TO_LOG:              bool  = False  # записывать ли дебаги в файл
TZ:                        str   = "UTC" # временная зона (Europe/Kyiv)


# SIGNAL:
# base signal
DIFF_PCT:       float = 2.0           # % отклонения справедливой цены от горячей. fear > hot
SIGNAL_TTL:     float = 0.5 * 60       # 1 минутa. Если сигнал продержался в течение этого времени то его считать подтвержденным.

# add signal
TREND_LINE = {
    "5m": {
        "enable": True,   # включен ли индикатор
        "fast": 10,       # длина короткой волны EMA       
        "slow": 30        # длина длинной волны EMA  
    }
}


# CREDO
BINANCE_API_PUBLIC_KEY:  str = "Vz2ImnNehZn8fCpsnUn7cUcaBCZ5TuS5RW4CqCUZH2pxcv9KUzCvXOgxJygXw1yc"  # публичный ключ Бинанс
BINANCE_API_PRIVATE_KEY: str = "h0uGoxCeDF9U2mk0NJvWvKld0rTsoV0pWFyCgqoH78NFRIicAXYf6KHkh6GCIitB"  # приватный ключ Бинанс
# TG_BOT_TOKEN:            str = "8287838939:AAHNUiNy4reI7-9D1N0PXHBdVX9EJ4Xx04A" # tir parser
TG_BOT_TOKEN:            str = "8204523080:AAGpm2vT3LK6EZzb34DfQOfUTXn9bF2MClk"   # test tir bot
# CHAT_ID_1:               str = "-1003036628247" # tir parser id
CHAT_ID_1:               str = "-1003339944736" # tir parser id

PROXY_LIST: List = [
    # {
    #     "enable": True,                     # флаг активности прокси
    #     "proxy_address": '154.222.214.132', # ...
    #     "proxy_port": '62890',
    #     "proxy_login": '1FDJcwJR',
    #     "proxy_password": 'U2yrFg4a'
    # },
    # {
    #     "enable": True,
    #     "proxy_address": '154.218.20.43',
    #     "proxy_port": '64630',
    #     "proxy_login":'1FDJcwJR',
    #     "proxy_password": 'U2yrFg4a'
    # },
    # {
    #     "enable": True,
    #     "proxy_address": '45.192.135.214',
    #     "proxy_port": '59100',
    #     "proxy_login":'nikolassmsttt0Icgm',
    #     "proxy_password": 'agrYpvDz7D'
    # },
    {
        "enable": True,
        "proxy_address": '154.218.20.43',
        "proxy_port": '64630',
        "proxy_login":'1FDJcwJR',
        "proxy_password": 'U2yrFg4a'
    },
    None  # локальный ip адрес
]
# curl -x 'http://154.218.20.43:64630' --proxy-user '1FDJcwJR:U2yrFg4a' https://ipinfo.io/json