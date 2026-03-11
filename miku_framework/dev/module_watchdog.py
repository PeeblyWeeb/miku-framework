import asyncio
import time
from collections.abc import Callable

from watchdog.events import (
    DirModifiedEvent,
    FileModifiedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)


class AsyncModuleWatchdog(FileSystemEventHandler):
    def __init__(self, async_callback: Callable, loop: asyncio.AbstractEventLoop, debounce: float = 0.1) -> None:
        super().__init__()
        self.callback = async_callback
        self.loop = loop
        self.debounce = debounce
        self._last_call = 0

    def _handle(self, event: FileSystemEvent):
        if not isinstance(event, FileModifiedEvent):
            return
        if not str(event.src_path).endswith(".py"):
            return

        now = time.time()
        if now - self._last_call < self.debounce:
            return
        self._last_call = now

        asyncio.run_coroutine_threadsafe(self.callback(), self.loop)

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent):
        self._handle(event)
