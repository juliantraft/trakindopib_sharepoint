"""
Simple logging setup suitable for automation systems that runs periodically in the background.
"""

from logging import Filter, Logger, LoggerAdapter, LogRecord, getLogger
from typing import Mapping, override
from uuid import uuid4

from src.utils import get_main_path

from .handlers import (
    LEVEL_MAPPING,
    LogLevel,
    NtfyHandler,
    TelegramHandler,
    get_daily_fh,
    get_stream_handler,
)
from .formatters import JSONFormatter


__all__ = [
    'RUN_ID',
    'Logger',
    'LoggerContext',
    'enable_ntfy_logging',
    'enable_telegram_logging',
    'getLogger',
    'init_logging',
    'suppress_logger',
]

RUN_ID = uuid4().hex[:8]
JSON_DELAY = 0.000001 # plase don't hate me for this


class LoggerContext(LoggerAdapter):
    """
    Slightly improved `LoggerAdapter` implementation, allowing `extra` values
    set during instantiation to be merged with `extra` given during log calls.
    """

    def __init__(self, logger: Logger | LoggerAdapter, extra: Mapping[str, object]):
        if isinstance(logger, Logger):
            base_logger = logger
        elif isinstance(logger, LoggerAdapter):
            base_logger = logger.logger
            if logger.extra is not None:
                extra = dict(logger.extra) | dict(extra)
        else:
            raise TypeError(f'{type(logger)} not supported')

        super().__init__(base_logger, extra)

    @override
    def process(self, msg: str, kwargs):
        kwargs['extra'] = self.extra | kwargs['extra'] if kwargs.get('extra') else self.extra
        return msg, kwargs


class LogContextFilter(Filter):
    """
    `Filter` subclass used to configure global `extra` metadata to all log entries.
    """

    def __init__(self):
        self.context: dict[str, object] = {}
        super().__init__('LogContextFilter')

    @override
    def filter(self, record: LogRecord) -> bool:
        record.run_id = RUN_ID
        for attr, val in self.context.items():
            setattr(record, attr, val)
        return True
    
    def add_context(self, context: dict[str, object]) -> None:
        self.context.update(context)

    def del_context(self, attr_name: str | list[str] | None):
        if attr_name is None:
            self.context = {}
            return
        
        # normalize into list
        if isinstance(attr_name, str):
            attr_name = [attr_name]
        
        for attr in attr_name:
            self.context.pop(attr, None)


def init_logging(debug: bool = False, fh_backup_count: int = 100) -> Logger:
    """
    Initializes the root logger with a rotating file handler and JSON formatting.

    Note:
    - Import and execute this function inside the application's entry point.
    - Tip: use `argparse` to toggle debug mode.

    Args:
        debug (bool): If `True` the Logger level will be set to `DEBUG` and logs
            from all logger will also output to the console.
        backup_count (int): Number of log files kept before rollover.
            Default is `100`.

    Returns:
        Logger: Root logger with its `name` replaced with the entry point filename.


    Examples:
        logs folder output example:
    ```
    logs/
        main.log
        main.log.2026-01-02
        main.log.2026-01-01
    ```
    """
    # get entry point file name
    main_name: str = get_main_path().stem

    root_logger: Logger = getLogger()
    root_logger.name = main_name
    root_logger.handlers.clear()
    root_logger.setLevel(LEVEL_MAPPING['DEBUG'] if debug else LEVEL_MAPPING['INFO'])

    json_fmt = JSONFormatter(
        fmt_keys={
            'timestamp': 'time',
            'run_id': 'run_id',
            'levelname': 'lv',
            'name': 'logger',
            'message': 'msg',
        },
        delay=JSON_DELAY
    )
    fh = get_daily_fh(main_name, fh_backup_count, fmt=json_fmt)
    fh.addFilter(LogContextFilter())

    root_logger.addHandler(fh)
    if debug:
        root_logger.addHandler(get_stream_handler())

    root_logger.info('INIT (debug)' if debug else 'INIT')
    return root_logger


def add_log_context(context: dict[str, object], logger_name: str | None = None) -> None:
    """
    Adds `extra` argument to all log entries.
    If a key already exist, it will be updated.

    Args:
        context (dict[str, object]): Extra key-value pair to be added to logs
        logger_name (str): Name of the logger
            (if not set, context will be added to root logger)
    """
    for h in getLogger(logger_name).handlers:
        for f in h.filters:
            if isinstance(f, LogContextFilter):
                f.add_context(context)


def del_log_context(
    attr_name: str | list[str] | None = None, logger_name: str | None = None
) -> None:
    """
    Delete specific or all `extra` argument in the gloal log context.
    If no key is provided, all arguments are removed.

    Args:
        attr_name (str | list[str] | None, optional): Extra key(s). 
        logger_name (str): Name of the logger
            (if not set, context will be added to root logger)
    """
    for h in getLogger(logger_name).handlers:
        for f in h.filters:
            if isinstance(f, LogContextFilter):
                f.del_context(attr_name)


def enable_telegram_logging(
    bot_token: str,
    chat_id: int,
    logger_name: str | None = None,
    level: LogLevel = 'CRITICAL'
) -> None:
    """
    Adds `TelegramHandler` to a logger. Posts only `CRITICAL` level logs by default.

    Args:
        bot_token (str): Token obtained from **BotFather**.
        chat_id (int): ID of the target chat.
        logger_name (str | None): Name of the logger
            (if not set, handler will be added to the root logger).
    """
    logger: Logger = getLogger(logger_name)
    logger.addHandler(TelegramHandler(bot_token, chat_id, level))


def enable_ntfy_logging(
    topic_url: str,
    logger_name: str | None = None,
    level: LogLevel = 'CRITICAL'
) -> None:
    """
    Adds `NtfyHandler` to a logger. Posts only `CRITICAL` level logs by default.

    Args:
        topic_url (str): Example: "https://ntfy.sh/my-topic"
        logger_name (str | None): Name of the logger
            (if not set, handler will be added to the root logger).
    """
    logger: Logger = getLogger(logger_name)
    logger.addHandler(NtfyHandler(topic_url, level))


def suppress_logger(name: str) -> None:
    """
    Suppress a logger by name. Useful for silencing library-specific logs.

    Args:
        name (str): Name of the logger (ex: `asyncio`)
    """
    logger: Logger = getLogger(name)
    logger.setLevel(LEVEL_MAPPING['ERROR'])
