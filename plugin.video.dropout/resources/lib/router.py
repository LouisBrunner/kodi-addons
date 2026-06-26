from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode

from .addon import Addon
from .api import API
from .utils import log_message


class Router:
    def __init__(self, *, default_action: str) -> None:
        self.__routes: dict[str, Callable] = {}
        self.__default_action = default_action
        self.__settings = Addon.settings()
        self.__api = API(credentials=Addon.credentials())

    def route(self, fn: Callable) -> Callable:
        name = fn.__name__  # ty:ignore[unresolved-attribute]
        if name in self.__routes:
            msg = f"duplicate action name: {name}"
            raise ValueError(msg)
        self.__routes[name] = fn
        return fn

    def dispatch(self, path: str) -> None:
        params = dict(parse_qsl(path))

        all_params = {**params, "api": self.__api, "sttngs": self.__settings}
        all_params.pop("action", None)

        name = params.get("action", self.__default_action)
        log_message(f"dispatching: {path} to {name}")

        action = self.__routes.get(name)
        if action is None:
            msg = f"Unsupported action {params['action']}"
            raise ValueError(msg)

        res = action(**all_params)
        if res is not None:
            res.render()

    def url_for(self, fn_or_action: Callable | str, **kwargs: Any) -> str:
        action = fn_or_action if isinstance(fn_or_action, str) else fn_or_action.__name__  # ty:ignore[unresolved-attribute]
        if action not in self.__routes:
            msg = f"Unsupported action {action}"
            raise ValueError(msg)
        qs = urlencode({**kwargs, "action": action})
        return f"plugin://{Addon.ID}?{qs}"
