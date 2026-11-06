import datetime as dt
from dataclasses import dataclass

from resources.lib.patch import monkey_patch

monkey_patch()


@dataclass
class Settings:
    email: str
    password: str


NOW = dt.datetime(2026, 6, 30, 10, tzinfo=dt.UTC)
