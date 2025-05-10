import os
import sys
import traceback

import xbmc
from xbmc import LOGDEBUG, LOGERROR, LOGINFO, LOGNONE, LOGWARNING

from .addon import Addon

_ = [LOGINFO, LOGDEBUG, LOGWARNING, LOGERROR, LOGNONE]

local_dev_mode = os.getenv("LOCAL_DEV_MODE") is not None


def _log(msg: str, level: int = LOGDEBUG) -> None:
    if local_dev_mode:
        print(f"[{level}] {msg}")
    else:
        xbmc.log(msg, level=level)


def log_message(message: str, *, level: int = LOGDEBUG) -> None:
    if level == LOGNONE:
        return
    if Addon.debug() and (level == LOGDEBUG):
        level = LOGINFO
    _log(f"{Addon.ID}: {message}", level=level)


def log_exception(message: str) -> None:
    exc_typ, exc, tb = sys.exc_info()
    if exc_typ is None or exc is None or tb is None:
        return
    _log(
        f"{Addon.ID}: {message} {''.join(traceback.format_exception(exc_typ, exc, tb))}",
        level=LOGERROR,
    )
