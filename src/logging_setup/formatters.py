from datetime import datetime, timezone
from json import dumps as json_dumps
from logging import Formatter, LogRecord
from socket import gethostname
from time import sleep
from typing import override


LOG_RECORD_ATTRS = {
    'args',
    'asctime',
    'created',
    'exc_info',
    'exc_text',
    'filename',
    'funcName',
    'levelname',
    'levelno',
    'lineno',
    'message',
    'module',
    'msecs',
    'msg',
    'name',
    'pathname',
    'process',
    'processName',
    'relativeCreated',
    'stack_info',
    'taskName',
    'thread',
    'threadName',
    # custom
    'timestamp',
    'run_id',
}


class JSONFormatter(Formatter):
    def __init__(self, *, fmt_keys: dict[str, str] | None = None, delay: float = 0.0):
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}
        self.delay = delay

    @override
    def format(self, record: LogRecord) -> str:
        sleep(self.delay)
        msg = self._get_log_dict(record)
        return json_dumps(msg, default=str)

    def _get_log_dict(self, record: LogRecord):
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        formatted_keys = {
            'timestamp': timestamp.isoformat(timespec='microseconds'),
            'message': record.getMessage(),
        }

        msg = {}
        record_dict = record.__dict__
        for key, alias in self.fmt_keys.items():
            if key in formatted_keys:
                msg[alias] = formatted_keys.get(key)
            elif key in record_dict:
                msg[alias] = record_dict.get(key)

        for key in record_dict:
            if key not in LOG_RECORD_ATTRS:
                msg[key] = record_dict[key]

        # exc_info may be a False
        if record.exc_info:
            msg['exc_info'] = self.formatException(record.exc_info)
        if record.stack_info is not None:
            msg['stack_info'] = self.formatStack(record.stack_info)

        return msg


class NtfyFormatter(Formatter):
    def __init__(self):
        super().__init__()

    @override
    def format(self, record: LogRecord) -> str:

        time: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        context: list[str] = []
        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_ATTRS:
                context.append(f'{key}={val}')

        msg = (
            f'[{record.levelname}] {time}\n'
            f'Machine: **{gethostname()}**\n'
            f'Module: **{record.pathname}**\n'
            f'Context: `{", ".join(context)}`\n\n---\n\n'
            f'> {record.getMessage()}'
        )

        # exc_info may be a False
        if record.exc_info:
            msg += '\n\n---\n\n' + self.formatException(record.exc_info)
        if record.stack_info is not None:
            msg += '\n\n---\n\n' + self.formatStack(record.stack_info)

        return msg
