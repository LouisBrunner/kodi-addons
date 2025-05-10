import sys
from typing import Tuple

import xbmcaddon
import xbmcvfs

from .config import Config
from .settings import Settings

_ID = "plugin.video.dropout"
_XBMC = xbmcaddon.Addon(_ID)


class Addon:
    ID = _ID
    XBMC = _XBMC
    PATH = _XBMC.getAddonInfo("path")
    CONFIG = Config(xbmcvfs.translatePath(f"special://profile/addon_data/{_ID}"))

    @classmethod
    def handle(cls) -> int:
        return int(sys.argv[1])

    @classmethod
    def debug(cls) -> bool:
        return cls.XBMC.getSettings().getBool("debug_mode")

    @classmethod
    def credentials(cls) -> Tuple[str, str]:
        return (
            cls.XBMC.getSettings().getString("username"),
            cls.XBMC.getSettings().getString("password"),
        )

    @classmethod
    def reset_credentials(cls) -> None:
        cls.XBMC.setSetting("username", "")
        cls.XBMC.setSetting("password", "")

    @classmethod
    def settings(cls) -> Settings:
        return Settings()
