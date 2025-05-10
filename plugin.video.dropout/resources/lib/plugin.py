# ruff: noqa: E402
from .patch import monkey_patch

monkey_patch()

import sys

from .addon import Addon
from .api import API
from .language import _
from .router import Router
from .settings import Settings
from .ui import Dialog, Folder, notify, play_video, refresh, render_page
from .utils import log_message

router = Router(default_action="home")


def dispatch():
    path = sys.argv[2][1:]
    log_message(f"entered with: {path}")

    router.dispatch(path)


@router.route
def home(*, sttngs: Settings, api: API):
    folder = Folder(_.HOME_TITLE)

    if not api.logged_in:
        folder.add_folder(router=router, label=_.LOGIN, path=router.url_for(login))
    elif not api.has_subscription:
        folder.add_folder(
            router=router, label=_.LOGIN_WITH_SUBSCRIPTION, path=router.url_for(login)
        )
    else:
        folder.add_folder(
            router=router, label=_.FEATURED, path=router.url_for(featured)
        )
        folder.add_folder(
            router=router,
            label=_.CONTINUE_WATCHING,
            path=router.url_for(continue_watching),
        )
        folder.add_folder(router=router, label=_.MY_LIST, path=router.url_for(my_list))
        folder.add_folder(
            router=router, label=_.NEW_RELEASES, path=router.url_for(new_releases)
        )
        folder.add_folder(
            router=router, label=_.TRENDING, path=router.url_for(trending)
        )
        folder.add_folder(router=router, label=_.SERIES, path=router.url_for(series))
        folder.add_folder(router=router, label=_.BROWSE, path=router.url_for(browse))
        folder.add_folder(router=router, label=_.SEARCH, path=router.url_for(search))

        folder.add_folder(router=router, label=_.LOGOUT, path=router.url_for(logout))

    return folder


@router.route
def login(*, sttngs: Settings, api: API):
    return Dialog(
        title=_.LOGIN_TITLE,
        message=_.LOGIN_MESSAGE,
        on_ok=lambda: settings(sttngs=sttngs, api=api),
    )


@router.route
def featured(*, sttngs: Settings, api: API, page: str = "1"):
    return render_page(
        router,
        action="featured",
        title=_.FEATURED,
        page=api.get_featured(page=int(page)),
    )


@router.route
def continue_watching(*, sttngs: Settings, api: API, page: str = "1"):
    return render_page(
        router,
        action="continue_watching",
        title=_.CONTINUE_WATCHING,
        content="episodes",
        page=api.get_continue_watching(page=int(page)),
    )


@router.route
def my_list(*, sttngs: Settings, api: API, page: str = "1"):
    return render_page(
        router, action="my_list", title=_.MY_LIST, page=api.get_my_list(page=int(page))
    )


@router.route
def new_releases(*, sttngs: Settings, api: API, page: str = "1"):
    return render_page(
        router,
        action="new_releases",
        title=_.NEW_RELEASES,
        page=api.get_new_releases(page=int(page)),
        content="episodes",
    )


@router.route
def trending(*, sttngs: Settings, api: API, page: str = "1"):
    return render_page(
        router,
        action="trending",
        content="tvshows",
        title=_.TRENDING,
        page=api.get_trending(page=int(page)),
    )


@router.route
def series(*, sttngs: Settings, api: API, page: str = "1"):
    return render_page(
        router,
        action="series",
        content="tvshows",
        title=_.SERIES,
        page=api.get_series(page=int(page)),
    )


@router.route
def browse(*, sttngs: Settings, api: API, page: str = "1"):
    return render_page(
        router, action="browse", title=_.BROWSE, page=api.get_browse(page=int(page))
    )


@router.route
def search(*, sttngs: Settings, api: API):
    pass
    # custom


@router.route
def logout(*, sttngs: Settings, api: API):
    return Dialog(
        title=_.LOGOUT_TITLE,
        message=_.LOGOUT_MESSAGE,
        on_ok=lambda: (
            api.logout(),
            Addon.reset_credentials(),
            refresh(),
        ),
    )


@router.route
def settings(*, sttngs: Settings, api: API):
    return Addon.XBMC.openSettings()


@router.route
def show_collection(
    *, sttngs: Settings, api: API, collection_id: str = "", collection_page: str = ""
):
    pass


@router.route
def show_series(*, sttngs: Settings, api: API, entity_id: str):
    pass


@router.route
def play(*, sttngs: Settings, api: API, slug: str = "", id: str = ""):
    if slug != "":
        media, data = api.playable_from_slug(slug)
    elif id != "":
        media, data = api.playable_from_id(int(id))
    else:
        raise ValueError("No slug or id provided")
    return play_video(router, media, data)


@router.route
def add_to_list(*, sttngs: Settings, api: API, entity_type: str, entity_id: str):
    if not api.add_to_list(entity_type, int(entity_id)):
        return
    notify(_.NOTIFY_ADD_TO_LIST, time=3000)
    return refresh()


@router.route
def remove_from_list(*, sttngs: Settings, api: API, entity_type: str, entity_id: str):
    if not api.remove_from_list(entity_type, int(entity_id)):
        return
    notify(_.NOTIFY_REMOVE_FROM_LIST, time=3000)
    return refresh()
