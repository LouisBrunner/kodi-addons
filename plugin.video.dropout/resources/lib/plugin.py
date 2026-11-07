# ruff: noqa: E402

# FIXME(3.9): drop in 3.10/11
from __future__ import annotations

from .patch import monkey_patch

monkey_patch()


import xbmc

from .addon import Addon
from .api import Profile
from .language import _
from .router import Context, Router
from .ui import Dialog, Folder, ProfileDialog, TextDialog, notify, play_video, refresh, render_page
from .utils import log_message

router = Router(default_action="home")


def dispatch(args: list[str]) -> None:
    if len(args) < 3:  # noqa: PLR2004
        msg = f"Invalid arguments: {args}"
        raise ValueError(msg)

    handle = int(args[1])
    path = args[2][1:]
    log_message(f"entered with: {path}")

    router.dispatch(handle, path)


@router.route
def home(*, ctx: Context) -> Folder:
    folder = Folder(_.HOME_TITLE, ctx=ctx)

    if ctx.api.stage == "login":
        folder.add_folder(router=router, label=_.LOGIN, path=router.url_for(login))
    elif ctx.api.stage == "nosub":
        folder.add_folder(router=router, label=_.LOGIN_WITH_SUBSCRIPTION, path=router.url_for(login))
    elif ctx.api.stage == "profile-select":
        if ctx.api.just_logged_in:
            select_profile(ctx=ctx).render()
            ctx.api.just_logged_in = False
        folder.add_folder(router=router, label=_.SELECT_PROFILE, path=router.url_for(select_profile))
        folder.add_folder(router=router, label=_.LOGOUT, path=router.url_for(logout))
    else:
        folder.add_folder(router=router, label=_.FEATURED, path=router.url_for(featured))
        folder.add_folder(
            router=router,
            label=_.CONTINUE_WATCHING,
            path=router.url_for(continue_watching),
        )
        folder.add_folder(router=router, label=_.MY_LIST, path=router.url_for(my_list))
        folder.add_folder(router=router, label=_.NEW_RELEASES, path=router.url_for(new_releases))
        folder.add_folder(router=router, label=_.TRENDING, path=router.url_for(trending))
        folder.add_folder(router=router, label=_.SERIES, path=router.url_for(series))
        folder.add_folder(router=router, label=_.BROWSE, path=router.url_for(browse))
        folder.add_folder(router=router, label=_.SEARCH, path=router.url_for(search))

        folder.add_folder(router=router, label=_.SELECT_PROFILE, path=router.url_for(select_profile))
        folder.add_folder(router=router, label=_.LOGOUT, path=router.url_for(logout))

    return folder


@router.route
def login(*, ctx: Context) -> Dialog:
    return Dialog(
        title=_.SUBSCRIPTION_REQUIRED,
        message=_.LOGIN_MESSAGE,
        on_ok=lambda: settings(ctx=ctx),
    )


@router.route
def select_profile(*, ctx: Context) -> ProfileDialog:
    player = xbmc.Player()
    if player.isPlaying():
        player.stop()

    def _on_select(profile: Profile, pin: str | None) -> bool:
        return ctx.api.select_profile(profile.index, pin)

    def _on_done() -> None:
        refresh()

    return ProfileDialog(
        profiles=ctx.api.get_profiles(),
        current=Addon.CONFIG.get_profile(),
        on_select=_on_select,
        on_done=_on_done,
    )


@router.route
def featured(*, ctx: Context, page: str = "1") -> Folder:
    return render_page(router, ctx=ctx, action="featured", title=_.FEATURED, page=ctx.api.get_featured(page=int(page)))


@router.route
def continue_watching(*, ctx: Context, page: str = "1") -> Folder:
    return render_page(
        router,
        ctx=ctx,
        action="continue_watching",
        title=_.CONTINUE_WATCHING,
        content="episodes",
        page=ctx.api.get_continue_watching(page=int(page)),
    )


@router.route
def my_list(*, ctx: Context, page: str = "1") -> Folder:
    return render_page(router, ctx=ctx, action="my_list", title=_.MY_LIST, page=ctx.api.get_my_list(page=int(page)))


@router.route
def new_releases(*, ctx: Context, page: str = "1") -> Folder:
    return render_page(
        router,
        ctx=ctx,
        action="new_releases",
        title=_.NEW_RELEASES,
        page=ctx.api.get_new_releases(page=int(page)),
        content="episodes",
    )


@router.route
def trending(*, ctx: Context, page: str = "1") -> Folder:
    return render_page(
        router,
        ctx=ctx,
        action="trending",
        content="tvshows",
        title=_.TRENDING,
        page=ctx.api.get_trending(page=int(page)),
    )


@router.route
def series(*, ctx: Context, page: str = "1") -> Folder:
    return render_page(
        router, ctx=ctx, action="series", content="tvshows", title=_.SERIES, page=ctx.api.get_all_series(page=int(page))
    )


@router.route
def browse(*, ctx: Context, page: str = "1") -> Folder:
    return render_page(router, ctx=ctx, action="browse", title=_.BROWSE, page=ctx.api.get_browse(page=int(page)))


@router.route
def search(*, ctx: Context) -> Folder:
    folder = Folder(_.SEARCH, ctx=ctx)
    folder.add_folder(
        router=router,
        label=_.NEW_SEARCH,
        path=router.url_for(new_search),
        special_sort="top",
    )
    searches = Addon.CONFIG.get_searches()
    searches = sorted(searches, key=lambda s: s.first, reverse=True)
    for search in searches:
        log_message(f"Adding search: {search}")
        folder.add_folder(
            router=router,
            label=search.search,
            path=router.url_for(search_results, search=search.search),
            contexts=[
                (
                    _(_.REMOVE_SEARCH),
                    f"RunPlugin({router.url_for(remove_search, search=search.search)})",
                ),
            ],
        )
    return folder


@router.route
def remove_search(*, ctx: Context, search: str) -> None:  # noqa: ARG001
    Addon.CONFIG.remove_search(search)
    return refresh()


@router.route
def new_search(*, ctx: Context) -> TextDialog:  # noqa: ARG001
    def _on_ok(search: str) -> None:
        Addon.CONFIG.add_search(search)
        xbmc.executebuiltin(f"RunPlugin({router.url_for(search_results, search=search)})")

    return TextDialog(
        title=_.SEARCH,
        on_ok=_on_ok,
    )


@router.route
def search_results(*, ctx: Context, search: str, page: str = "1") -> Folder:
    return render_page(
        router,
        ctx=ctx,
        action="search_results",
        title=_(_.SEARCH_RESULTS_FOR).format(query=search),
        page=ctx.api.search(query=search, page=int(page)),
        extra={"search": search},
    )


@router.route
def logout(*, ctx: Context) -> Dialog:
    def _on_ok() -> None:
        ctx.api.logout()
        Addon.reset_credentials()
        refresh()

    return Dialog(
        title=_.LOGOUT,
        message=_.LOGOUT_MESSAGE,
        on_ok=_on_ok,
    )


@router.route
def settings(*, ctx: Context) -> None:  # noqa: ARG001
    return Addon.XBMC.openSettings()


@router.route
def show_collection(
    *,
    ctx: Context,
    collection_id: str,
    page: str = "1",
) -> Folder:
    cid = int(collection_id)
    collection = ctx.api.get_collection(cid)
    return render_page(
        router,
        ctx=ctx,
        action="show_collection",
        title=collection.name,
        page=ctx.api.get_collection_items(collection=cid, page=int(page)),
        extra={"collection_id": collection_id},
    )


@router.route
def show_series(*, ctx: Context, entity_id: str, page: str = "1") -> Folder:
    sid = int(entity_id)
    series = ctx.api.get_series(sid)
    return render_page(
        router,
        ctx=ctx,
        action="show_series",
        title=series.title,
        page=ctx.api.get_collection_items(collection=sid, page=int(page)),
        extra={"entity_id": entity_id},
    )


@router.route
def show_season(*, ctx: Context, entity_id: str, page: str = "1") -> Folder:
    sid = int(entity_id)
    season = ctx.api.get_season(sid)
    return render_page(
        router,
        ctx=ctx,
        action="show_season",
        title=season.title,
        page=ctx.api.get_collection_items(collection=sid, page=int(page)),
        extra={"entity_id": entity_id},
        content="episodes",
    )


@router.route
def play(*, ctx: Context, slug: str = "", id: str = "") -> None:
    if slug != "":
        media, data = ctx.api.playable_from_slug(slug)
    elif id != "":
        media, data = ctx.api.playable_from_id(int(id))
    else:
        msg = "No slug or id provided"
        raise ValueError(msg)
    return play_video(router, ctx=ctx, media=media, data=data)


@router.route
def add_to_list(*, ctx: Context, entity_type: str, entity_id: str) -> None:
    if not ctx.api.add_to_list(entity_type, int(entity_id)):
        return None
    notify(_.NOTIFY_ADD_TO_LIST, time=3000)
    return refresh()


@router.route
def remove_from_list(*, ctx: Context, entity_type: str, entity_id: str) -> None:
    if not ctx.api.remove_from_list(entity_type, int(entity_id)):
        return None
    notify(_.NOTIFY_REMOVE_FROM_LIST, time=3000)
    return refresh()
