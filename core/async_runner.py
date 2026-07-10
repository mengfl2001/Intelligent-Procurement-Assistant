import asyncio
import threading
from queue import Queue
from typing import Any, Callable, Optional


class AsyncRunner:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._result_queue: Queue = Queue()
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop(self):
        if not self._running or not self._loop:
            return
        self._running = False
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)

    def submit(self, coro, callback: Optional[Callable[[Any], None]] = None):
        if not self._loop or not self._running:
            raise RuntimeError("AsyncRunner not started")

        def done_callback(future):
            try:
                result = future.result()
                if callback:
                    callback(result)
            except Exception as e:
                if callback:
                    callback(e)

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        future.add_done_callback(done_callback)
        return future

    def get_result(self, block: bool = False, timeout: Optional[float] = None):
        return self._result_queue.get(block=block, timeout=timeout)

    def put_result(self, result: Any):
        self._result_queue.put(result)

    @property
    def running(self):
        return self._running

    @property
    def loop(self):
        return self._loop


async_runner = AsyncRunner()