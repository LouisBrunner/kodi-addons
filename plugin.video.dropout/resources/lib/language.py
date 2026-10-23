from typing import Literal

import xbmc

from .addon import Addon
from .utils import LOGWARNING, log_message

_ADDON_STRINGS_START = 30000


class Language:
    SEARCH = 137
    BROWSE = 1024
    CONTINUE_WATCHING = 13362
    NOTIFY_PIN_INCORRECT = 19265
    NEW_SEARCH = 19335
    LOGOUT = 20126
    SETTINGS = 21417

    LOGIN = 32101
    MY_LIST = 32103
    NEW_RELEASES = 32104
    TRENDING = 32105
    SERIES = 32106
    SUBSCRIPTION_REQUIRED = 32110
    LOGIN_MESSAGE = 32111
    HOME_TITLE = 32112
    LOGIN_WITH_SUBSCRIPTION = 32113
    ADD_TO_LIST = 32116
    REMOVE_FROM_LIST = 32117
    LOGOUT_MESSAGE = 32119
    FEATURED = 32120
    PAGE_TITLE = 32122
    NEXT_PAGE = 32123
    PREVIOUS_PAGE = 32124
    NOTIFY_ADD_TO_LIST = 32125
    NOTIFY_REMOVE_FROM_LIST = 32126
    GO_TO_SERIES = 32128
    SEARCH_RESULTS_FOR = 32132
    REMOVE_SEARCH = 32133
    GO_TO_SEASON = 32134
    SELECT_PROFILE = 32135
    PROFILE_WITH_PIN = 32136
    ENTER_PIN = 32137

    @classmethod
    def __call__(cls, uid: int) -> str:
        text = Addon.XBMC.getLocalizedString(uid) if uid >= _ADDON_STRINGS_START else xbmc.getLocalizedString(uid)
        if text == "":
            log_message(f"missing string {uid}", level=LOGWARNING)
            text = f"missing string {uid}"
        return text

    @classmethod
    def region(cls, uid: Literal["dateshort", "datelong", "time", "meridiem", "tempunit", "speedunit"]) -> str:
        return xbmc.getRegion(uid)


_ = Language()
