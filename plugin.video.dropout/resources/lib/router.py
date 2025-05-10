from typing import Callable, Dict
from urllib.parse import parse_qsl, urlencode

from .addon import Addon
from .api import API
from .utils import log_message


class Router:
    def __init__(self, *, default_action: str) -> None:
        self.__routes: Dict[str, Callable] = {}
        self.__default_action = default_action
        self.__settings = Addon.settings()
        self.__api = API(credentials=Addon.credentials())

    def route(self, fn: Callable) -> Callable:
        name = fn.__name__
        if name in self.__routes:
            raise ValueError(f"duplicate action name: {name}")
        self.__routes[name] = fn
        return fn

    def dispatch(self, path: str) -> None:
        params = dict(parse_qsl(path))

        all_params = {**params, "api": self.__api, "sttngs": self.__settings}
        if "action" in all_params:
            del all_params["action"]

        name = params.get("action", self.__default_action)
        log_message(f"dispatching: {path} to {name}")

        action = self.__routes.get(name)
        if action is None:
            raise ValueError(f"Unsupported action {params['action']}")

        res = action(**all_params)
        if res is not None:
            res.render()

    def url_for(self, fn_or_action: Callable | str, **kwargs) -> str:
        if isinstance(fn_or_action, str):
            action = fn_or_action
        else:
            action = fn_or_action.__name__
        if action not in self.__routes:
            raise ValueError(f"Unsupported action {action}")
        qs = urlencode({**kwargs, "action": action})
        return f"plugin://{Addon.ID}?{qs}"
