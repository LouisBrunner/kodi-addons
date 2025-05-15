import os
from typing import Callable, Dict, List, Optional, Tuple

import xbmc
import xbmcgui
import xbmcplugin

from .addon import Addon
from .api import (
    Assets,
    Collection,
    Movie,
    PaginatedMedia,
    Playable,
    Season,
    Series,
    UnreleasedVideo,
    Video,
    VideoData,
    thumbnail_formatter,
)
from .language import _
from .router import Router
from .utils import LOGWARNING, log_message

KODI_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class Folder:
    def __init__(
        self,
        name: int | str,
        *,
        content: str = "episodes",
        total_items: Optional[int] = None,
    ) -> None:
        self.__handle = Addon.handle()
        self.__total_items = total_items
        xbmcplugin.setPluginCategory(
            self.__handle, _(name) if isinstance(name, int) else name
        )
        xbmcplugin.setContent(self.__handle, content)

    @classmethod
    def __get_settings_menu(cls, router: Router) -> Tuple[str, str]:
        return (
            _(_.SETTINGS),
            f"RunPlugin({router.url_for('settings')})",
        )

    def add_folder(
        self,
        *,
        router: Router,
        label: int | str,
        path: str,
        special_sort: Optional[str] = None,
        contexts: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        if isinstance(label, int):
            label = _(label)
        list_item = xbmcgui.ListItem(label=label, path=path)
        list_item.setProperty("IsPlayable", "false")
        if special_sort is not None:
            list_item.setProperty("SpecialSort", special_sort)
        list_item.setArt(
            {
                "icon": os.path.join(Addon.PATH, "icon.png"),
                "thumb": os.path.join(Addon.PATH, "fanart.png"),
                "fanart": os.path.join(Addon.PATH, "fanart.png"),
                "landscape": os.path.join(Addon.PATH, "fanart.png"),
                "poster": os.path.join(Addon.PATH, "poster.png"),
            }
        )
        list_item.addContextMenuItems(
            [
                *(contexts if contexts is not None else []),
                self.__get_settings_menu(router),
            ],
            replaceItems=True,
        )
        xbmcplugin.addDirectoryItem(self.__handle, path, list_item, True)

    @classmethod
    def __assets_to_arts(cls, assets: Assets) -> Dict[str, str]:
        arts = {
            "icon": assets.icon,
            "poster": assets.poster,
            "fanart": assets.fanart,
            "banner": assets.banner,
            "thumb": assets.thumb,
            "landscape": assets.landscape,
        }
        delete = []
        for k, v in arts.items():
            if v is None:
                delete.append(k)
            arts[k] = thumbnail_formatter(v, art=k)
        for k in delete:
            del arts[k]
        return arts

    @classmethod
    def __thumbnail_to_arts(cls, thumbnail: str) -> Dict[str, str]:
        return {
            "poster": thumbnail_formatter(thumbnail, art="poster"),
            "fanart": thumbnail_formatter(thumbnail, art="fanart"),
            "banner": thumbnail_formatter(thumbnail, art="banner"),
            "thumb": thumbnail_formatter(thumbnail, art="thumb"),
            "landscape": thumbnail_formatter(thumbnail, art="landscape"),
        }

    @classmethod
    def __add_prefix(cls, prefix: str, name: str) -> str:
        if Addon.debug():
            return f"{prefix} | {name}"
        return name

    @classmethod
    def info_for_playable(
        cls, *, router: Router, video: Playable, path: str
    ) -> xbmcgui.ListItem:
        list_item = xbmcgui.ListItem(
            label=cls.__add_prefix("VID", video.title),
            label2=video.short_description,
            path=path,
        )
        list_item.setProperty(Addon.PLAYER_VIDEO_ID, str(video.entity_id))
        list_item.setProperty("IsPlayable", "true")
        if isinstance(video, Movie):
            list_item.setArt(cls.__assets_to_arts(video.assets))
        else:
            list_item.setArt(cls.__thumbnail_to_arts(video.thumbnail))

        list_item.setInfo("video", {})

        info_tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
        info_tag.setTitle(video.title)
        info_tag.setPlotOutline(video.short_description)
        info_tag.setTagLine(video.short_description)
        info_tag.setPlot(video.description)
        info_tag.setDateAdded(video.created_at.strftime(KODI_DATETIME_FORMAT))
        info_tag.setDuration(video.duration_s)

        contextmenu = []
        if isinstance(video, Movie):
            if video.trailer_url is not None:
                if isinstance(video.trailer_url, int):
                    path = router.url_for("play", id=video.trailer_url)
                else:
                    path = router.url_for(
                        "play", slug=os.path.basename(video.trailer_url)
                    )
                info_tag.setTrailer(path)
            info_tag.setMediaType("movie")

        if isinstance(video, UnreleasedVideo):
            info_tag.setMediaType("video")

        else:
            info_tag.setTags(video.tags)
            if video.release_dates is not None and len(video.release_dates) > 0:
                info_tag.setFirstAired(
                    video.release_dates[0].date.strftime(KODI_DATETIME_FORMAT)
                )
                info_tag.setYear(video.release_dates[0].date.year)
                info_tag.setCountries([video.release_dates[0].location])

            if video.season is not None:
                info_tag.setTvShowTitle(video.season.name)
                info_tag.setSeason(video.season.number)
                if video.season.episode_number is not None:
                    info_tag.setEpisode(video.season.episode_number)
                info_tag.setMediaType("episode")
            else:
                info_tag.setMediaType("video")

            if video.series is not None:
                contextmenu.append(
                    (
                        _(_.GO_TO_SERIES),
                        f"RunPlugin({router.url_for('show_series', entity_id=video.series.id)})",
                    )
                )

            if video.play_state is not None:
                info_tag.setResumePoint(video.play_state.duration_s, video.duration_s)
                info_tag.setLastPlayed(
                    video.play_state.last_seen.strftime(KODI_DATETIME_FORMAT)
                )
                if video.play_state.completed:
                    info_tag.setPlaycount(1)

            if not isinstance(video, Movie):
                contextmenu.append(
                    (
                        _(_.GO_TO_SEASON),
                        f"RunPlugin({router.url_for('show_season', entity_id=video.collection_id)})",
                    )
                )

        typ = "video" if isinstance(video, Video) else "movie"
        if video.is_in_list:
            contextmenu.insert(
                0,
                (
                    _(_.REMOVE_FROM_LIST),
                    f"RunPlugin({router.url_for('remove_from_list', entity_type=typ, entity_id=video.entity_id)})",
                ),
            )
        else:
            contextmenu.insert(
                0,
                (
                    _(_.ADD_TO_LIST),
                    f"RunPlugin({router.url_for('add_to_list', entity_type=typ, entity_id=video.entity_id)})",
                ),
            )
        contextmenu.append(cls.__get_settings_menu(router))
        list_item.addContextMenuItems(
            contextmenu,
            replaceItems=True,
        )

        return list_item

    def add_video(
        self,
        *,
        router: Router,
        video: Playable,
    ) -> None:
        path = router.url_for(
            "play",
            slug=video.trailer_slug
            if isinstance(video, UnreleasedVideo)
            else video.slug,
        )

        list_item = self.info_for_playable(router=router, video=video, path=path)

        xbmcplugin.addDirectoryItem(
            self.__handle,
            path,
            list_item,
            isFolder=False,
            totalItems=self.__total_items if self.__total_items else 0,
        )

    def add_series(
        self,
        *,
        router: Router,
        series: Series,
    ) -> None:
        path = router.url_for("show_series", entity_id=series.entity_id)

        list_item = xbmcgui.ListItem(
            label=self.__add_prefix("SER", series.title),
            label2=series.short_description,
            path=path,
        )
        list_item.setProperty("IsPlayable", "false")
        list_item.setArt(self.__assets_to_arts(series.assets))
        list_item.setInfo("video", {})

        info_tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
        info_tag.setTitle(series.title)
        info_tag.setPlotOutline(series.short_description)
        info_tag.setTagLine(series.short_description)
        info_tag.setPlot(series.description)
        info_tag.setDateAdded(series.created_at.strftime(KODI_DATETIME_FORMAT))
        # FIXME: if we set a trailer on a folder, then clicking the folder tries (and fails) to play the trailer
        if series.trailer_url is not None and False:
            path = None
            if isinstance(series.trailer_url, int):
                path = router.url_for("play", id=series.trailer_url)
            else:
                path = router.url_for("play", slug=os.path.basename(series.trailer_url))
            info_tag.setTrailer(path)
        info_tag.setMediaType("tvshow")
        for i in range(series.seasons):
            info_tag.addSeason(i + 1)

        contextmenu = []
        if series.is_in_list:
            contextmenu.append(
                (
                    _(_.REMOVE_FROM_LIST),
                    f"RunPlugin({router.url_for('remove_from_list', entity_type='series', entity_id=series.entity_id)})",
                )
            )
        else:
            contextmenu.append(
                (
                    _(_.ADD_TO_LIST),
                    f"RunPlugin({router.url_for('add_to_list', entity_type='series', entity_id=series.entity_id)})",
                )
            )
        list_item.addContextMenuItems(
            contextmenu,
            replaceItems=True,
        )
        xbmcplugin.addDirectoryItem(
            self.__handle,
            path,
            list_item,
            isFolder=True,
            totalItems=self.__total_items if self.__total_items else 0,
        )

    def add_season(
        self,
        *,
        router: Router,
        season: Season,
    ) -> None:
        path = router.url_for("show_season", entity_id=season.entity_id)

        list_item = xbmcgui.ListItem(
            label=self.__add_prefix("SEA", season.title), path=path
        )
        list_item.setProperty("IsPlayable", "false")
        list_item.setArt(self.__thumbnail_to_arts(season.thumbnail))
        list_item.setInfo("video", {})

        info_tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
        info_tag.setTitle(season.title)
        info_tag.setDateAdded(season.created_at.strftime(KODI_DATETIME_FORMAT))
        # FIXME: if we set a trailer on a folder, then clicking the folder tries (and fails) to play the trailer
        if season.trailer_url is not None and False:
            path = None
            if isinstance(season.trailer_url, int):
                path = router.url_for("play", id=season.trailer_url)
            else:
                path = router.url_for("play", slug=os.path.basename(season.trailer_url))
            info_tag.setTrailer(path)
        info_tag.setMediaType("season")
        info_tag.setSeason(season.season_number)

        contextmenu = []
        if season.is_in_list:
            contextmenu.append(
                (
                    _(_.REMOVE_FROM_LIST),
                    f"RunPlugin({router.url_for('remove_from_list', entity_type='series', entity_id=season.entity_id)})",
                )
            )
        else:
            contextmenu.append(
                (
                    _(_.ADD_TO_LIST),
                    f"RunPlugin({router.url_for('add_to_list', entity_type='series', entity_id=season.entity_id)})",
                )
            )
        list_item.addContextMenuItems(
            contextmenu,
            replaceItems=True,
        )
        xbmcplugin.addDirectoryItem(
            self.__handle,
            path,
            list_item,
            isFolder=True,
            totalItems=self.__total_items if self.__total_items else 0,
        )

    def add_collection(
        self,
        *,
        router: Router,
        collection: Collection,
    ) -> None:
        path = router.url_for("show_collection", collection_id=collection.entity_id)

        list_item = xbmcgui.ListItem(
            label=self.__add_prefix("COL", collection.name),
            label2=collection.short_description or "",
            path=path,
        )
        list_item.setProperty("IsPlayable", "false")
        if isinstance(collection.thumbnail, str):
            list_item.setArt(self.__thumbnail_to_arts(collection.thumbnail))
        else:
            list_item.setArt(self.__assets_to_arts(collection.thumbnail))
        list_item.setInfo("video", {})

        info_tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
        info_tag.setTitle(collection.name)
        info_tag.setTagLine(collection.short_description or collection.name)
        if collection.description is not None:
            info_tag.setPlot(collection.description)
        if collection.short_description is not None:
            info_tag.setPlotOutline(collection.short_description)
        if collection.created_at is not None:
            info_tag.setDateAdded(collection.created_at.strftime(KODI_DATETIME_FORMAT))
        info_tag.setMediaType("tvshow")

        contextmenu = []
        if collection.is_in_list:
            contextmenu.append(
                (
                    _(_.REMOVE_FROM_LIST),
                    f"RunPlugin({router.url_for('remove_from_list', entity_type='collection', entity_id=collection.entity_id)})",
                )
            )
        else:
            contextmenu.append(
                (
                    _(_.ADD_TO_LIST),
                    f"RunPlugin({router.url_for('add_to_list', entity_type='collection', entity_id=collection.entity_id)})",
                )
            )
        list_item.addContextMenuItems(
            contextmenu,
            replaceItems=True,
        )
        xbmcplugin.addDirectoryItem(
            self.__handle,
            path,
            list_item,
            isFolder=True,
            totalItems=self.__total_items if self.__total_items else 0,
        )

    def render(self):
        xbmcplugin.endOfDirectory(self.__handle, cacheToDisc=False)


class Dialog:
    def __init__(self, *, title: int, message: int, on_ok: Callable[[], None]) -> None:
        self.__title = _(title)
        self.__message = _(message)
        self.__on_ok = on_ok

    def render(self):
        dialog = xbmcgui.Dialog()
        if dialog.ok(self.__title, self.__message):
            self.__on_ok()


class TextDialog:
    def __init__(self, *, title: int, on_ok: Callable[[str], None]) -> None:
        self.__title = _(title)
        self.__on_ok = on_ok

    def render(self) -> None:
        dialog = xbmcgui.Dialog()
        res = dialog.input(self.__title)
        if res != "":
            self.__on_ok(res)


def render_page(
    router: Router,
    *,
    action: str,
    title: int | str,
    page: PaginatedMedia,
    content: str = "videos",
) -> Folder:
    folder = Folder(
        _(_.PAGE_TITLE).format(
            page=page.page, title=_(title) if isinstance(title, int) else title
        ),
        content="videos",
        total_items=len(page.items),
    )
    if page.page > 1:
        kwargs = {}
        if page.page > 2:
            kwargs["page"] = page.page - 1
        folder.add_folder(
            router=router,
            label=_(_.PREVIOUS_PAGE).format(page=page.page - 1),
            path=router.url_for(
                action,
                **kwargs,
            ),
            special_sort="top",
        )
    for medium in page.items:
        if isinstance(medium, Video) or isinstance(medium, Movie):
            folder.add_video(router=router, video=medium)
        elif isinstance(medium, Collection):
            folder.add_collection(router=router, collection=medium)
        elif isinstance(medium, Series):
            folder.add_series(router=router, series=medium)
        elif isinstance(medium, Season):
            folder.add_season(router=router, season=medium)
        else:
            log_message(f"Unknown medium type: {type(medium)}", level=LOGWARNING)
    if page.next_page is not None:
        folder.add_folder(
            router=router,
            label=_(_.NEXT_PAGE).format(page=page.next_page),
            path=router.url_for(
                action,
                page=page.next_page,
            ),
            special_sort="bottom",
        )
    return folder


def refresh() -> None:
    xbmc.executebuiltin("Container.Refresh")


def notify(message: int, *, time: int) -> None:
    addon_name = Addon.XBMC.getAddonInfo("name")
    addon_icon = Addon.XBMC.getAddonInfo("icon")
    xbmc.executebuiltin(
        f"Notification({addon_name}, {_(message)}, {time}, {addon_icon})"
    )


def play_video(router: Router, media: Playable, data: VideoData) -> None:
    li = Folder.info_for_playable(router=router, video=media, path=data.url)
    li.setMimeType(data.mime_type)
    li.setSubtitles(data.subtitles)
    xbmcplugin.setResolvedUrl(Addon.handle(), succeeded=True, listitem=li)
