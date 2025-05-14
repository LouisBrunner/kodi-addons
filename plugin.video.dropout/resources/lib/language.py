from .addon import Addon
from .utils import LOGWARNING, log_message


class Language:
    LOGIN = 32101
    CONTINUE_WATCHING = 32102
    MY_LIST = 32103
    NEW_RELEASES = 32104
    TRENDING = 32105
    SERIES = 32106
    SEARCH = 32107
    LOGOUT = 32108
    SETTINGS = 32109
    LOGIN_TITLE = 32110
    LOGIN_MESSAGE = 32111
    HOME_TITLE = 32112
    LOGIN_WITH_SUBSCRIPTION = 32113
    ADD_TO_LIST = 32116
    REMOVE_FROM_LIST = 32117
    LOGOUT_TITLE = 32118
    LOGOUT_MESSAGE = 32119
    FEATURED = 32120
    BROWSE = 32121
    PAGE_TITLE = 32122
    NEXT_PAGE = 32123
    PREVIOUS_PAGE = 32124
    NOTIFY_ADD_TO_LIST = 32125
    NOTIFY_REMOVE_FROM_LIST = 32126
    GO_TO_SERIES = 32128
    SEASON_TITLE = 32129
    SPECIFIC_SEASON_TITLE = 32130
    NEW_SEARCH = 32131
    SEARCH_RESULTS_FOR = 32132
    REMOVE_SEARCH = 32133
    GO_TO_SEASON = 32134

    @classmethod
    def __call__(cls, id: int) -> str:
        text = Addon.XBMC.getLocalizedString(id)
        if text == "":
            log_message(f"missing string {id}", level=LOGWARNING)
            text = f"missing string {id}"
        return text


_ = Language()
