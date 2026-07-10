import logging
import os
from queue import Queue
from typing import Optional

from core.async_runner import async_runner


class UILogHandler(logging.Handler):
    def __init__(self, queue: Queue):
        super().__init__()
        self._queue = queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self._queue.put(msg)
        except Exception:
            self.handleError(record)


class Logger:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self._log_queue: Queue = Queue()
        self._logger = logging.getLogger("SmartPurchaseAgent")
        self._logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler(
            os.path.join("logs", "smart_purchase_agent.log"),
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)

        ui_handler = UILogHandler(self._log_queue)
        ui_handler.setLevel(logging.INFO)
        ui_handler.setFormatter(formatter)
        self._logger.addHandler(ui_handler)

    def info(self, message: str):
        self._logger.info(message)

    def debug(self, message: str):
        self._logger.debug(message)

    def warning(self, message: str):
        self._logger.warning(message)

    def error(self, message: str):
        self._logger.error(message)

    def critical(self, message: str):
        self._logger.critical(message)

    def get_log(self, block: bool = False, timeout: Optional[float] = None):
        try:
            return self._log_queue.get(block=block, timeout=timeout)
        except:
            return None

    @property
    def queue(self):
        return self._log_queue


logger = Logger()