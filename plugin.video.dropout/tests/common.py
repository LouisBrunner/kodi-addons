import datetime
from dataclasses import dataclass

from resources.lib.patch import monkey_patch

monkey_patch()


@dataclass
class Settings:
    email: str
    password: str


NOW = datetime.datetime(2026, 6, 30, 10, tzinfo=datetime.timezone.utc)
