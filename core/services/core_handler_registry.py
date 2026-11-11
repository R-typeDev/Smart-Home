
from threading import RLock
from typing import Any


class CoreHandlerRegistry:
    """Registry for universal Core device handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, Any] = {}
        self._lock = RLock()

    def register(self, handler: Any) -> None:
        handler_id = getattr(handler, "handler_id", None)

        if not handler_id:
            raise ValueError("Core handler must define handler_id")

        with self._lock:
            self._handlers[handler_id] = handler

    def unregister(self, handler_id: str) -> None:
        with self._lock:
            self._handlers.pop(handler_id, None)

    def is_registered(self, handler_id: str) -> bool:
        with self._lock:
            return handler_id in self._handlers

    def get(self, handler_id: str) -> Any:
        with self._lock:
            handler = self._handlers.get(handler_id)

        if handler is None:
            raise LookupError(f"Core handler '{handler_id}' is not registered")

        return handler

    def call(
        self,
        handler_id: str,
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        handler = self.get(handler_id)
        function = getattr(handler, method, None)

        if not callable(function):
            raise AttributeError(
                f"Core handler '{handler_id}' has no method '{method}'"
            )

        return function(*args, **kwargs)

    def get_all_ids(self) -> list[str]:
        with self._lock:
            return list(self._handlers)


core_handler_registry = CoreHandlerRegistry()
