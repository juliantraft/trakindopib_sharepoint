from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    FileHandler,
    Formatter,
    Handler,
    StreamHandler,
)
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from re import sub
from socket import gethostname
from sys import stderr, stdout
from typing import Literal, TextIO

from requests import post

from src.utils import get_main_path

from .formatters import NtfyFormatter


PROJECT_DIR: Path = get_main_path().parent
LOGS_DIR: Path = PROJECT_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)


type LogLevel = Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

LEVEL_MAPPING: dict[str, int] = {
    'DEBUG': DEBUG,
    'INFO': INFO,
    'WARNING': WARNING,
    'ERROR': ERROR,
    'CRITICAL': CRITICAL
}
STREAM_MAPPING: dict[str, TextIO] = {
    'stderr': stderr,
    'stdout': stdout,
}

sh_fmt: str = '%(asctime)s.%(msecs)d [%(levelname)s] (%(name)s) %(message)s'
fh_fmt: str = '%(asctime)s [%(levelname)s] (%(name)s) %(message)s'


def get_stream_handler(
    stream: Literal['stderr', 'stdout'] = 'stderr',
    level: LogLevel = 'DEBUG',
    fmt: Formatter | None = None,
) -> StreamHandler:
    fmt = Formatter(fmt=sh_fmt, datefmt='%H:%M:%S') if fmt is None else fmt
    sh = StreamHandler(STREAM_MAPPING[stream])
    sh.setFormatter(fmt)
    sh.setLevel(LEVEL_MAPPING[level])
    return sh


def get_file_handler(
    filename: str, level: LogLevel = 'INFO', fmt: Formatter | None = None
) -> FileHandler:
    fmt = Formatter(fmt=fh_fmt) if fmt is None else fmt
    fh = FileHandler(LOGS_DIR / f'{filename}.log', encoding='utf-8')
    fh.setFormatter(fmt)
    fh.setLevel(LEVEL_MAPPING[level])
    return fh


def get_daily_fh(
    filename: str,
    backup_count: int = 100,
    level: LogLevel = 'INFO',
    fmt: Formatter | None = None,
) -> TimedRotatingFileHandler:
    daily_fh = TimedRotatingFileHandler(
        filename=LOGS_DIR / f'{filename}.log',
        encoding='utf-8',
        when='midnight',
        interval=1,
        backupCount=backup_count,
        utc=False,
    )
    fmt = Formatter(fmt=fh_fmt) if fmt is None else fmt
    daily_fh.setFormatter(fmt)
    daily_fh.setLevel(LEVEL_MAPPING[level])
    return daily_fh


# -------------------------------------------------------------------------------
#   Custom Telegram Handler
# -------------------------------------------------------------------------------


class TelegramHandler(Handler):
    def __init__(self, bot_token: str, chat_id: int, level: LogLevel = 'CRITICAL'):
        super().__init__()
        self.bot_token: str = bot_token
        self.chat_id: int = chat_id

        hostname: str = gethostname()
        self.setFormatter(
            Formatter(
                fmt=f'[%(levelname)s] %(asctime)s\n'
                    f'Machine: <b>{hostname}</b>\n'
                    f'Application: <b><u>%(pathname)s</u></b>\n\n'
                    f'%(message)s'
            )
        )
        self.setLevel(LEVEL_MAPPING[level])

    def emit(self, record):
        try:
            raw_entry: str = self.format(record)
            formatted_entry: str = sub(r'"([^"]+)"', r'<u>\1</u>', raw_entry)

            url: str = f'https://api.telegram.org/bot{self.bot_token}/sendMessage'
            payload: dict = {
                'chat_id': self.chat_id,
                'text': formatted_entry,
                'parse_mode': 'HTML',
            }
            post(url, data=payload)
        except Exception:
            self.handleError(record)


# -------------------------------------------------------------------------------
#   Custom ntfy.sh Handler
# -------------------------------------------------------------------------------


class NtfyHandler(Handler):
    def __init__(self, topic_url: str, level: LogLevel = 'CRITICAL') -> None:
        super().__init__()
        self.topic_url: str = topic_url
        self.setFormatter(NtfyFormatter())
        self.setLevel(LEVEL_MAPPING[level])

    def emit(self, record):
        try:
            post(
                url=self.topic_url,
                data=self.format(record).encode('utf-8'),
                headers={'Markdown': 'yes'},
            )
        except Exception:
            self.handleError(record)
