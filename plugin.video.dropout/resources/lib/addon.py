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
    PLAYER_VIDEO_ID = f"{_ID}.video_id"

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
    def use_inputstream_adaptive(cls) -> bool:
        return (
            cls.XBMC.getSettings().getBool("use_inputstream_adaptive")
            and cls.is_inputstream_adaptive_available()
        )

    @classmethod
    def is_inputstream_adaptive_available(cls) -> bool:
        try:
            addon = xbmcaddon.Addon("inputstream.adaptive")
            return addon is not None
        except RuntimeError:
            return False

    @classmethod
    def settings(cls) -> Settings:
        return Settings()
