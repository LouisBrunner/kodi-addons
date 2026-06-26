import datetime
import hashlib
import html
import json
import re
from dataclasses import dataclass
from typing import Any, ClassVar
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from .addon import Addon
from .config import Credentials, PlayState
from .utils import LOGDEBUG, LOGERROR, LOGNONE, LOGWARNING, log_message

REQUEST_TIMEOUT_S = (10, 30)

TOKEN_FINDER = r'(?s)window\.VHX\.config\s*=\s*{.*token:\s*"([^"]*)",'  # noqa: S105
USER_FINDER = r'_current_user":{"id":([^,]+),"'
EMBED_FINDER = r'(?s)window\.VHX\.config\s*=\s*{.*embed_url:\s*"([^"]*)",'
CONFIG_FINDER = r"(?s)window\.OTTData\s*=\s*({.*})\s*</script>"
EMBED_ID_FINDER = r"https://embed\.vhx\.tv/videos/(\d+)\?"
COLLECTION_ID_FINDER = r"https://api\.vhx\.tv/collections/(\d+)/items"


@dataclass
class Assets:
    icon: str | None
    poster: str | None
    fanart: str
    landscape: str
    banner: str | None
    thumb: str


@dataclass
class Collection:
    entity_id: int
    slug: str
    name: str
    items_count: int
    thumbnail: str | Assets
    short_description: str | None
    description: str | None
    created_at: datetime.datetime | None
    updated_at: datetime.datetime | None
    is_in_list: bool = False


@dataclass
class Series:
    entity_id: int
    collection_page: str | None
    title: str
    slug: str
    short_description: str
    description: str
    seasons: int
    trailer_url: str | int | None
    assets: Assets
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_in_list: bool = False


@dataclass
class VideoSeries:
    name: str
    id: int


@dataclass
class VideoSeason:
    name: str
    number: int
    episode_number: int | None


@dataclass
class VideoReleaseDate:
    date: datetime.date
    location: str


@dataclass
class UnreleasedVideo:
    entity_id: int
    title: str
    trailer_slug: str
    short_description: str
    description: str
    duration_s: int
    thumbnail: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_in_list: bool = False


@dataclass
class ReleasedVideo:
    entity_id: int
    collection_id: int
    title: str
    slug: str
    short_description: str
    description: str
    url: str
    duration_s: int
    series: VideoSeries | None
    season: VideoSeason | None
    thumbnail: str
    tags: list[str]
    release_dates: list[VideoReleaseDate] | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    play_state: PlayState | None = None
    is_in_list: bool = False


Video = UnreleasedVideo | ReleasedVideo


@dataclass(kw_only=True)
class Movie(ReleasedVideo):
    assets: Assets
    trailer_url: str | int | None


@dataclass
class Season:
    entity_id: int
    title: str
    slug: str
    season_number: int
    episodes_count: int
    trailer_url: str | int | None
    thumbnail: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_in_list: bool = False


Media = Collection | Series | Season | Video | Movie
Playable = Video | Movie


@dataclass
class PaginatedMedia:
    items: list[Media]
    page: int
    next_page: int | None


@dataclass
class VideoData:
    subtitles: list[str]
    url: str
    mime_type: str


_VHX_SITE_ID = 36348
_VHX_PRODUCT_ID = 28599
_VHX_NEW_RELEASES_ID = 129054
_VHX_ALL_SERIES_ID = 243176
_VHX_TRENDING_ID = 1151509


# TODO: is it worth caching using If-None-Match?


class API:
    WEBSITE_URL = "https://watch.dropout.tv"
    REFERER_URL = "https://watch.dropout.tv"
    API_URL_COM = "https://api.vhx.com"
    API_URL_TV = "https://api.vhx.tv"
    API_PREFIX = f"/v2/sites/{_VHX_SITE_ID}"

    DEFAULT_PER_PAGE = 25

    def __init__(self, *, credentials: tuple[str, str]) -> None:
        self.__credentials = credentials

        self.__session = requests.session()
        cookies = requests.utils.cookiejar_from_dict(Addon.CONFIG.get_cookie_jar())
        self.__session.cookies.update(cookies)

        self.__my_list: set[int] | None = None
        self.__token = None
        self.__user_id = None

        self.logged_in = False
        self.has_subscription = False

        creds = Addon.CONFIG.get_credentials()

        self.__ensure_logged_in(creds)

        if creds is None and self.logged_in and self.has_subscription:
            assert self.__token is not None  # noqa: S101
            assert self.__user_id is not None  # noqa: S101
            log_message(f"caching credentials {self.__token}/{self.__user_id}", level=LOGDEBUG)
            Addon.CONFIG.set_credentials(
                Credentials(
                    hash=self.__calculate_hash(),
                    token=self.__token,
                    user_id=self.__user_id,
                    when=datetime.datetime.now(tz=datetime.UTC),
                )
            )

    def __calculate_hash(self) -> str:
        username, password = self.__credentials
        return hashlib.md5(f"{username}{password}".encode()).hexdigest()  # noqa: S324

    def __ensure_logged_in(self, creds: Credentials | None) -> bool:
        if creds is not None:
            hashc = self.__calculate_hash()
            now = datetime.datetime.now(tz=datetime.UTC)
            if hashc == creds.hash and now - creds.when < datetime.timedelta(minutes=5):
                self.__token = creds.token
                self.__user_id = creds.user_id
                self.logged_in = True
                self.has_subscription = True
                log_message(
                    f"using cached credentials {self.__token}/{self.__user_id}",
                    level=LOGDEBUG,
                )
                return True
            log_message(
                f"not using cash {hashc} != {creds.hash} or expired {now - creds.when}",
                level=LOGDEBUG,
            )
            Addon.CONFIG.set_credentials(None)

        if self.__update_from_website():
            return True

        return self.__do_login()

    def __do_login(self) -> bool:
        username, password = self.__credentials
        if username == "" or password == "":
            log_message("no credentials set, cannot login", level=LOGWARNING)
            return False

        authenticity_token = self.__get_authenticity_token()

        log_message(
            f"trying to login with auth_token {authenticity_token}",
            level=LOGWARNING,
        )
        res = self.__website_request(
            "/login",
            method="POST",
            data={
                "email": username,
                "password": password,
                "authenticity_token": authenticity_token,
                "utf8": True,
            },
        )
        if not res.ok:
            log_message(
                f"login failed with {res.text}",
                level=LOGWARNING,
            )
            return False

        return self.__update_from_website()

    def __update_from_website(self) -> bool:
        self.__update_status()

        if self.logged_in:
            return self.__update_token()

        return False

    def __update_token(self) -> bool:
        res = self.__website_request("/")
        token_info = re.search(TOKEN_FINDER, res.text)
        user_info = re.search(USER_FINDER, res.text)
        self.__token = token_info.group(1) if token_info is not None else None
        self.__user_id = int(user_info.group(1)) if user_info is not None else None
        log_message(
            f"updating token with {token_info}/{user_info} => token={self.__token}, user_id={self.__user_id}",
            level=LOGDEBUG,
        )
        return token_info is not None and user_info is not None

    def __update_status(self) -> bool:
        res = self.__website_request("/customer_settings/subscription_plans")
        sub_plan = res.json()
        self.logged_in = sub_plan is not None
        self.has_subscription = sub_plan is not None and not sub_plan.get("current_plan", {}).get("has_expired", True)
        log_message(
            (
                f"updating status with {res}/{sub_plan} => logged_in={self.logged_in}, "
                f"has_subscription={self.has_subscription}"
            ),
            level=LOGDEBUG,
        )
        if sub_plan is None:
            self.__clear_auth_data()
        return sub_plan is not None

    def __get_authenticity_token(self, *, meta: bool = False) -> str:
        if meta:
            res = self.__website_request("/")
            soup = BeautifulSoup(res.text, "html.parser")
            meta_tag = soup.find("meta", {"name": "csrf-token"})
            if meta_tag is None:
                msg = "internal error: could not get authenticity token (meta not found)"
                raise ValueError(msg)
            token = meta_tag.attrs.get("content")
            if token is None or token == "":
                msg = "internal error: could not get authenticity token (token not found)"
                raise ValueError(msg)
            return str(token)

        res = self.__website_request("/login")
        soup = BeautifulSoup(res.text, "html.parser")

        form = soup.find(id="login-form-password")
        if form is None:
            msg = "internal error: could not get authenticity token (form not found)"
            raise ValueError(msg)
        inpt = form.find(attrs={"name": "authenticity_token"})
        if inpt is None:
            msg = "internal error: could not get authenticity token (input not found)"
            raise ValueError(msg)
        token = inpt.attrs.get("value")
        if token is None or token == "":
            msg = "internal error: could not get authenticity token (token not found)"
            raise ValueError(msg)
        return str(token)

    def __website_request(
        self,
        url: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
    ) -> requests.Response:
        log_message(
            f"making website request to {url} with data={data} and cookies={self.__session.cookies}",
            level=LOGNONE,
        )
        rep = self.__session.request(
            method,
            f"{self.WEBSITE_URL}{url}",
            data=data,
            timeout=REQUEST_TIMEOUT_S,
        )
        Addon.CONFIG.set_cookie_jar(requests.utils.dict_from_cookiejar(self.__session.cookies))
        log_message(
            f"website request to {url} returned {rep.status_code} with {rep.text}",
            level=LOGNONE,
        )
        return rep

    def logout(self) -> None:
        self.__website_request(
            "/logout",
            method="POST",
            data={"authenticity_token": self.__get_authenticity_token(meta=True)},
        )
        self.logged_in = False
        self.has_subscription = False
        self.__clear_auth_data()

    def __clear_auth_data(self) -> None:
        Addon.CONFIG.set_cookie_jar({})
        self.__session.cookies.clear()
        self.__token = None

    def __ensure_has_my_list(self) -> None:
        if self.__my_list is not None:
            return

        url = f"/customers/{self.__user_id}/watchlist"
        res = self.__api_request_pages(
            url,
            params={
                "product": _VHX_PRODUCT_ID,
                "collection": f"{self.API_URL_TV}{url}",
                "include_products": True,
            },
            use_tv=True,
        )
        final = self.__parse_media(res, from_tv=True, fast=True, is_my_list=True)
        self.__my_list = {i.entity_id for i in final}

    def get_new_releases(self, *, page: int = 1) -> PaginatedMedia:
        self.__ensure_has_my_list()
        return self.__get_from_collection(page=page, collection=_VHX_NEW_RELEASES_ID)

    def get_continue_watching(self, *, page: int = 1) -> PaginatedMedia:
        self.__ensure_has_my_list()
        res = self.__api_request(
            f"/users/{self.__user_id}/watching",
            params={
                "page": page,
                "per_page": self.DEFAULT_PER_PAGE,
                "include_events": 1,
                "include_collections": 1,
            },
            use_tv=False,
        )
        res = self.__parse_com_page(res, page)
        log_message(f"continue watching [FROM API]: {res}", level=LOGDEBUG)
        res.items = list(
            filter(
                lambda i: (
                    not isinstance(i, ReleasedVideo)
                    or i.play_state is None
                    or not i.play_state.completed
                    or not i.play_state.from_us
                ),
                res.items,
            )
        )
        log_message(f"continue watching [FILTERED]: {res}", level=LOGDEBUG)
        if page == 1:
            all_play_states = Addon.CONFIG.get_playstates()
            for i in res.items:
                if isinstance(i, Video) and i.entity_id in all_play_states:
                    del all_play_states[i.entity_id]
            all_play_states = dict(filter(lambda i: not i[1].completed, all_play_states.items()))
            log_message(f"continue watching [FROM CONFIG]: {all_play_states}", level=LOGDEBUG)
            extras = [self.__parse_playable(self.__get_video_by_id(i), embedded=True) for i in all_play_states]
            res.items.extend(extras)
            res.items = sorted(
                res.items,
                key=lambda i: (
                    i.play_state.last_seen
                    if isinstance(i, ReleasedVideo) and i.play_state is not None
                    else datetime.datetime.min
                ),
                reverse=True,
            )
        log_message(f"continue watching [WITH OURS]: {res}", level=LOGDEBUG)
        return res

    def get_my_list(self, *, page: int = 1) -> PaginatedMedia:
        url = f"/customers/{self.__user_id}/watchlist"
        res = self.__api_request(
            url,
            params={
                "page": page,
                "per_page": self.DEFAULT_PER_PAGE,
                "product": _VHX_PRODUCT_ID,
                "collection": f"{self.API_URL_TV}{url}",
                "include_products": True,
            },
            use_tv=True,
        )
        return self.__parse_tv_page(res, page, is_my_list=True)

    def __get_from_collection(self, *, page: int, collection: int, is_my_list: bool = False) -> PaginatedMedia:
        res = self.__api_request(
            f"/collections/{collection}/items",
            params={
                "page": page,
                "per_page": self.DEFAULT_PER_PAGE,
                "include_events": 1,
                "include_products_for": "web",
            },
            use_tv=False,
        )
        return self.__parse_com_page(res, page, is_my_list=is_my_list)

    def search(self, *, query: str, page: int) -> PaginatedMedia:
        self.__ensure_has_my_list()
        res = self.__api_request(
            "/search",
            params={
                "q": query,
                "type": ",".join(["video", "collection", "live_event", "product"]),  # noqa: FLY002
                "page": page,
                "per_page": self.DEFAULT_PER_PAGE,
            },
            use_tv=False,
        )
        return self.__parse_com_page(res, page, items="results")

    def __get_collection(self, collection: int, *, types: list[str]) -> dict:
        res = self.__api_request(f"/collections/{collection}", use_tv=False)
        if res is None:
            msg = f"could not get collection {collection}"
            raise ValueError(msg)
        log_message(
            f"collection {collection}: {res}",
            level=LOGDEBUG,
        )
        if res["type"] not in types:
            msg = f"invalid type for {collection} (expected {types}): {res}"
            raise ValueError(msg)
        return res

    def get_collection(self, collection: int) -> Collection:
        return self.__parse_collection(
            self.__get_collection(collection, types=["collection", "category"]),
            extended=True,
        )

    def get_series(self, series: int) -> Series:
        return self.__parse_series(self.__get_collection(series, types=["series"]))

    def get_season(self, season: int) -> Series:
        return self.__parse_series(self.__get_collection(season, types=["season"]))

    def get_collection_items(self, *, page: int, collection: int) -> PaginatedMedia:
        self.__ensure_has_my_list()
        return self.__get_from_collection(page=page, collection=collection)

    def get_all_series(self, *, page: int = 1) -> PaginatedMedia:
        self.__ensure_has_my_list()
        return self.__get_from_collection(page=page, collection=_VHX_ALL_SERIES_ID)

    def get_trending(self, *, page: int = 1) -> PaginatedMedia:
        self.__ensure_has_my_list()
        return self.__get_from_collection(page=page, collection=_VHX_TRENDING_ID)

    def get_featured(self, *, page: int = 1) -> PaginatedMedia:
        self.__ensure_has_my_list()
        res = self.__api_request(
            "/products/featured_items",
            params={
                "page": page,
                "per_page": self.DEFAULT_PER_PAGE,
                "site_id": _VHX_SITE_ID,
            },
            use_tv=True,
        )
        return self.__parse_tv_page(res, page)

    def get_browse(self, *, page: int = 1) -> PaginatedMedia:
        self.__ensure_has_my_list()
        res = self.__api_request(
            "/browse",
            params={
                "page": page,
                "per_page": self.DEFAULT_PER_PAGE,
                "include_events": 1,
                "include_products": True,
                "product": f"{self.API_URL_TV}/products/{_VHX_PRODUCT_ID}",
                "site_id": _VHX_SITE_ID,
            },
            use_tv=True,
        )
        return self.__parse_tv_page(res, page)

    def add_to_list(self, typ: str, uid: int) -> bool:
        return self.__x_from_list("PUT", typ, uid)

    def remove_from_list(self, typ: str, uid: int) -> bool:
        return self.__x_from_list("DELETE", typ, uid)

    def __x_from_list(self, method: str, typ: str, uid: int) -> bool:
        if typ == "movie":
            params = {"collection": uid}
        else:
            if typ == "series":
                typ = "collection"
            params = {typ: f"{self.API_URL_TV}/{typ}s/{uid}"}
        res = self.__api_request(
            "/me/watchlist",
            method=method,
            params=params,
            use_tv=True,
        )
        return res is not None

    def __api_request(
        self,
        url: str,
        *,
        use_tv: bool,
        method: str = "GET",
        params: dict[str, Any] | None = None,
    ) -> dict | None:
        base = self.API_URL_TV if use_tv else self.API_URL_COM
        extra_parts = [self.API_PREFIX] if not use_tv else []
        next_url = "".join([base, *extra_parts, url])
        log_message(
            f"making api request to {url} ({next_url}) with params={params} and token={self.__token}",
            level=LOGDEBUG,
        )
        res = requests.request(
            method,
            next_url,
            params=params,
            headers={
                "Authorization": f"Bearer {self.__token}",
            },
            timeout=REQUEST_TIMEOUT_S,
        )
        if not res.ok:
            msg = f"api request to {url} ({next_url}) failed with {res.status_code} and {res.text}"
            if Addon.debug():
                raise ValueError(msg)
            log_message(msg, level=LOGERROR)
            return None

        out = {}
        if res.status_code != 204:  # noqa: PLR2004
            out = res.json()

        log_message(
            f"api request to {url} ({next_url}) returned {res.status_code} with {out}",
            level=LOGDEBUG,
        )

        return out

    def __api_request_pages(
        self,
        url: str,
        *,
        use_tv: bool,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        base_url = self.API_URL_TV if use_tv else self.API_URL_COM
        extra_parts = [self.API_PREFIX] if not use_tv else []
        next_url = "".join([base_url, *extra_parts, url])
        log_message(
            f"making api request pages to {url} ({next_url}) with params={params} and token={self.__token}",
            level=LOGDEBUG,
        )
        items = []
        while True:
            res = requests.get(
                next_url,
                params=params,
                headers={
                    "Authorization": f"Bearer {self.__token}",
                },
                timeout=REQUEST_TIMEOUT_S,
            )
            if not res.ok:
                msg = f"api request pages to {url} ({next_url}) failed with {res.status_code} and {res.text}"
                if Addon.debug():
                    raise ValueError(msg)
                log_message(msg, level=LOGERROR)
                break
            log_message(
                f"api request pages to {url} ({next_url}) returned {res.status_code}",
                level=LOGDEBUG,
            )
            log_message(
                f"api request pages to {url} ({next_url}) returned {res.status_code} with {res.json()}",
                level=LOGNONE,
            )

            data = res.json()
            data_with_items = data
            if use_tv:
                data_with_items = data.get("_embedded", {})
            items.extend(data_with_items.get("items", []))

            if use_tv:
                next_url = data.get("_links", {}).get("next", {}).get("href")
                if next_url is None:
                    break
            else:
                pagination = data.get("pagination", {})
                if pagination["count"] <= pagination["page"] * pagination["per_page"]:
                    break
                next_url = pagination["template_url"].format(
                    page=pagination["page"] + 1, per_page=pagination["per_page"]
                )
        log_message(
            f"finished request to {url} with {len(items)} items",
            level=LOGDEBUG,
        )

        return items

    def __parse_com_page(
        self,
        res: dict | None,
        current_page: int,
        *,
        items: str = "items",
        is_my_list: bool = False,
    ) -> PaginatedMedia:
        if res is None:
            return PaginatedMedia(items=[], page=current_page, next_page=None)
        next_page = None
        pagination = res["pagination"]
        if pagination["count"] >= pagination["page"] * pagination["per_page"]:
            next_page = pagination["page"] + 1
        return PaginatedMedia(
            items=self.__parse_media(res[items], from_tv=False, is_my_list=is_my_list),
            page=pagination["page"],
            next_page=next_page,
        )

    def __parse_tv_page(self, res: dict | None, current_page: int, *, is_my_list: bool = False) -> PaginatedMedia:
        if res is None:
            return PaginatedMedia(items=[], page=current_page, next_page=None)
        next_page = None
        if res.get("_links", {}).get("next", {}).get("href") is not None:
            next_page = current_page + 1
        return PaginatedMedia(
            items=self.__parse_media(res["_embedded"]["items"], from_tv=True, is_my_list=is_my_list),
            page=current_page,
            next_page=next_page,
        )

    def __parse_medium(self, item: dict, *, from_tv: bool, is_my_list: bool = False) -> tuple[Media, bool]:  # noqa: ARG002
        is_embedded = True
        if "entity" in item:
            item = item["entity"]
            is_embedded = False
        need_play_state = False
        match item.get("type"):
            case "video":
                log_message(
                    f"found video {item}, embedded={is_embedded}",
                    level=LOGDEBUG,
                )
                media = self.__parse_video(item, embedded=is_embedded)
                if "_embedded" in item and "play_state" in item["_embedded"] and isinstance(media, ReleasedVideo):
                    media.play_state = self.__if_more_recent(
                        media.play_state,
                        self.__parse_play_state(item["_embedded"]["play_state"]),
                    )
                else:
                    need_play_state = isinstance(media, ReleasedVideo)
            case "movie":
                log_message(
                    f"found movie {item}, embedded={is_embedded}",
                    level=LOGDEBUG,
                )
                media = self.__parse_movie(item, embedded=is_embedded, is_my_list=is_my_list)
                need_play_state = True
            case "season":
                log_message(
                    f"found season {item}, embedded={is_embedded}",
                    level=LOGDEBUG,
                )
                media = self.__parse_season(item, embedded=is_embedded)
            case "series":
                log_message(
                    f"found series {item}, embedded={is_embedded}",
                    level=LOGDEBUG,
                )
                media = self.__parse_series(item, embedded=is_embedded)
            case None:
                log_message(
                    f"found collection {item}, embedded={is_embedded}",
                    level=LOGDEBUG,
                )
                media = self.__parse_collection(item, embedded=is_embedded)
            case _:
                msg = f"unknown type {item['type']}"
                raise ValueError(msg)
        if is_my_list:
            media.is_in_list = True
        elif self.__my_list is not None:
            media.is_in_list = media.entity_id in self.__my_list
        return media, need_play_state

    def __parse_media(
        self,
        items: list[dict],
        *,
        from_tv: bool,
        fast: bool = False,
        is_my_list: bool = False,
    ) -> list[Media]:
        out = []
        videos = []
        for item in items:
            try:
                media, need_play_state = self.__parse_medium(
                    item,
                    from_tv=from_tv,
                    is_my_list=is_my_list,
                )
                if need_play_state:
                    videos.append(len(out))
                out.append(media)
            except ValueError as e:
                log_message(
                    f"could not parse item {item}: {e}",
                    level=LOGWARNING,
                )

        if len(videos) > 0 and not fast:
            lookup = {out[i].entity_id: i for i in videos}
            pstates = self.__get_play_state(list(lookup.keys()))
            for ps in pstates:
                i = lookup.get(ps["video_id"])
                if i is None:
                    log_message(
                        f"could not find video {ps['video_id']} in lookup",
                        level=LOGWARNING,
                    )
                    continue
                vid = out[i]
                if not isinstance(vid, ReleasedVideo):
                    continue  # internal error!
                vid.play_state = self.__if_more_recent(vid.play_state, self.__parse_play_state(ps))

        return out

    def __parse_playable(self, item: dict, *, embedded: bool) -> Playable:
        if item.get("type") == "video":
            media = self.__parse_video(item, embedded=embedded)
            if isinstance(media, UnreleasedVideo):
                msg = f"cannot play unreleased video {item['id']}: {media}"
                raise ValueError(msg)
            if "_embedded" in item and "play_state" in item["_embedded"]:
                media.play_state = self.__if_more_recent(
                    media.play_state,
                    self.__parse_play_state(item["_embedded"]["play_state"]),
                )
                return media
        elif item.get("type") == "movie":
            media = self.__parse_movie(item, embedded=embedded)
        else:
            msg = f"unknown type {item['type']}"
            raise ValueError(msg)
        play_states = self.__get_play_state([media.entity_id])
        for ps in play_states:
            if ps["video_id"] == media.entity_id:
                media.play_state = self.__if_more_recent(media.play_state, self.__parse_play_state(ps))
                break
        return media

    def __if_more_recent(self, current: PlayState | None, parsed: PlayState) -> PlayState:
        if current is None:
            return parsed
        if parsed.last_seen > current.last_seen:
            return parsed
        return current

    def __parse_play_state(self, ps: dict) -> PlayState:
        return PlayState(
            completed=ps["completed"],
            duration_s=ps["duration"],
            timecode=ps["timecode"],
            last_seen=datetime.datetime.fromtimestamp(ps["timestamp"], tz=datetime.UTC),
        )

    def __get_play_state(self, video_ids: list[int]) -> list[dict]:
        data = self.__api_request(
            f"/users/{self.__user_id}/play_state",
            params={"video_ids": ",".join(map(str, video_ids))},
            use_tv=False,
        )
        if data is None:
            return []
        return data["entries"]

    def __parse_video(self, item: dict, *, embedded: bool = False) -> Video:
        dateformat = "%Y-%m-%dT%H:%M:%S.%fZ" if not embedded else "%Y-%m-%dT%H:%M:%SZ"
        if "metadata" not in item:
            return UnreleasedVideo(
                entity_id=item["id"],
                title=item["title"],
                trailer_slug=item["url"],
                short_description=item["short_description"],
                description=item["description"],
                duration_s=item["duration"]["seconds"],
                thumbnail=item["thumbnail"]["source"],
                created_at=datetime.datetime.strptime(item["created_at"], dateformat),
                updated_at=datetime.datetime.strptime(item["updated_at"], dateformat),
            )
        metadata = item["metadata"]
        series = None
        season = None
        if not embedded:
            if metadata["series"]["name"] is not None:
                series = VideoSeries(
                    name=metadata["series"]["name"],
                    id=int(metadata["series"]["id"]),
                )
        elif "series_name" in metadata and "series_id" in metadata:
            series = VideoSeries(
                name=metadata["series_name"],
                id=int(metadata["series_id"]),
            )
        if not embedded:
            if metadata["season"]["name"] is not None:
                season = VideoSeason(
                    name=metadata["season"]["name"],
                    number=int(metadata["season"]["number"]),
                    episode_number=int(metadata["season"]["episode_number"])
                    if metadata["season"].get("episode_number")
                    else None,
                )
        elif "season_name" in metadata and "season_number" in metadata:
            season = VideoSeason(
                name=metadata["season_name"],
                number=int(metadata["season_number"]),
                episode_number=int(metadata["episode_number"]) if metadata.get("episode_number") else None,
            )
        rdates = metadata["release_dates"] if not embedded else item["release_dates"]
        release_dates = None
        if rdates is not None:
            release_dates = [
                VideoReleaseDate(
                    date=datetime.datetime.strptime(rdate["date"], "%Y-%m-%d").date(),
                    location=rdate["location"],
                )
                for rdate in rdates
            ]
        thumbnail = item["thumbnails"]["16_9"]["source"] if not embedded else item["thumbnail"]["source"]
        url = item["page_url"] if not embedded else item["_links"]["video_page"]
        slug = item["slug"] if not embedded else item["url"]
        tags = metadata["tags"] if not embedded else item["tags"]
        return ReleasedVideo(
            entity_id=item["id"],
            collection_id=item["canonical_collection_id"],
            title=item["title"],
            slug=slug,
            short_description=item["short_description"],
            description=item["description"],
            url=url,
            duration_s=item["duration"]["seconds"],
            series=series,
            season=season,
            thumbnail=thumbnail,
            tags=tags if tags is not None else [],
            release_dates=release_dates,
            created_at=datetime.datetime.strptime(item["created_at"], dateformat),
            updated_at=datetime.datetime.strptime(item["updated_at"], dateformat),
            play_state=Addon.CONFIG.get_playstate(item["id"]),
        )

    def __assets_from_item(self, item: dict, *, embedded: bool = False) -> Assets:
        assets = None
        if embedded:
            adds = item["additional_images"]
            assets = Assets(
                icon=adds["aspect_ratio_1_1"]["source"] if "aspect_ratio_1_1" in adds else None,
                poster=adds["aspect_ratio_2_3"]["source"] if "aspect_ratio_2_3" in adds else None,
                fanart=adds["aspect_ratio_16_9_background"]["source"],
                landscape=adds["aspect_ratio_16_9_background"]["source"],
                banner=adds["aspect_ratio_16_6"]["source"] if adds["aspect_ratio_16_6"] is not None else None,
                thumb=item["thumbnail"]["source"],
            )
        else:
            thumbs = item["thumbnails"]
            t16_9 = thumbs["16_9"]["source"]
            t16_9_bg = thumbs["16_9_background"]
            t16_9_bg = t16_9_bg["source"] if t16_9_bg is not None else t16_9
            assets = Assets(
                icon=thumbs["1_1"]["source"],
                poster=thumbs["2_3"]["source"],
                fanart=t16_9_bg,
                landscape=t16_9_bg,
                banner=thumbs["16_6"]["source"] if thumbs.get("16_6") is not None else None,
                thumb=t16_9,
            )
        return assets

    def __parse_movie(self, item: dict, *, embedded: bool = False, is_my_list: bool = False) -> Movie:
        trailer_url = item.get("trailer_url") if embedded else item.get("trailer_video_id")
        page = self.__get_from_collection(page=1, collection=item["id"], is_my_list=is_my_list)
        vid = None
        for i in page.items:
            if not isinstance(i, Video):
                continue
            if vid is None or vid.duration_s > i.duration_s:
                vid = i
                break
        # FIXME: are some video unavailable then?
        if vid is None:
            msg = f"invalid type for collection (movie) {item['id']}: {page.items}"
            raise ValueError(msg)
        if len(page.items) > 1:
            log_message(
                f"found {len(page.items)} videos in collection {item['id']}, using {vid}, full list: {page.items}",
                level=LOGWARNING,
            )

        if not isinstance(vid, ReleasedVideo):
            msg = f"cannot use unreleased video for movie {item['id']}: {vid}"
            raise TypeError(msg)

        return Movie(
            entity_id=vid.entity_id,
            collection_id=vid.collection_id,
            title=vid.title,
            slug=vid.slug,
            short_description=vid.short_description,
            description=vid.description,
            url=vid.url,
            duration_s=vid.duration_s,
            series=vid.series,
            season=vid.season,
            thumbnail=vid.thumbnail,
            tags=vid.tags,
            release_dates=vid.release_dates,
            created_at=vid.created_at,
            updated_at=vid.updated_at,
            play_state=vid.play_state,
            is_in_list=vid.is_in_list,
            assets=self.__assets_from_item(item, embedded=embedded),
            trailer_url=trailer_url,
        )

    def __parse_season(self, item: dict, *, embedded: bool = False) -> Season:
        dateformat = "%Y-%m-%dT%H:%M:%S.%fZ" if not embedded else "%Y-%m-%dT%H:%M:%SZ"
        return Season(
            entity_id=item["id"],
            title=item["title"],
            slug=item["slug"],
            season_number=item["season_number"],
            episodes_count=item["episodes_count"],
            trailer_url=item.get("trailer_video_id"),
            thumbnail=item["thumbnails"]["16_9"]["source"],
            created_at=datetime.datetime.strptime(item["created_at"], dateformat),
            updated_at=datetime.datetime.strptime(item["updated_at"], dateformat),
        )

    def __parse_series(self, item: dict, *, embedded: bool = False) -> Series:
        dateformat = "%Y-%m-%dT%H:%M:%S.%fZ" if not embedded else "%Y-%m-%dT%H:%M:%SZ"
        collection_page = None
        if embedded:
            collection_page = item["_links"]["collection_page"]
        trailer_url = item.get("trailer_url") if embedded else item.get("trailer_video_id")
        title = item["name"] if embedded else item["title"]
        return Series(
            entity_id=item["id"],
            collection_page=collection_page,
            title=title,
            slug=item["slug"],
            short_description=item["short_description"],
            description=item["description"],
            seasons=item["seasons_count"],
            trailer_url=trailer_url,
            assets=self.__assets_from_item(item, embedded=embedded),
            created_at=datetime.datetime.strptime(item["created_at"], dateformat),
            updated_at=datetime.datetime.strptime(item["updated_at"], dateformat),
        )

    _RESERVED_CATEGORIES: ClassVar = [
        "featured",
        "continue-watching",
        "my-list",
        "new-releases",
        "trending",
        "all-series",
    ]

    def __parse_collection(self, item: dict, *, embedded: bool = False, extended: bool = False) -> Collection:
        dateformat = "%Y-%m-%dT%H:%M:%S.%fZ" if not embedded else "%Y-%m-%dT%H:%M:%SZ"
        slug = item["slug"]
        if slug in self._RESERVED_CATEGORIES:
            msg = "internal category, skipping"
            raise ValueError(msg)
        iid = item.get("id")
        if iid is None:
            link_info = re.search(COLLECTION_ID_FINDER, item["_links"]["items"]["href"])
            if link_info is None:
                msg = "could not find id in collection"
                raise ValueError(msg)
            iid = int(link_info.group(1))
        name = None
        name = item["title"] if extended else item["name"]
        assets = None
        assets = self.__assets_from_item(item, embedded=embedded) if extended else item["thumbnail"]["source"]
        return Collection(
            entity_id=iid,
            slug=slug,
            name=name,
            items_count=item["items_count"],
            thumbnail=assets,
            short_description=item["short_description"] if extended else None,
            description=item["description"] if extended else None,
            created_at=datetime.datetime.strptime(item["created_at"], dateformat) if extended else None,
            updated_at=datetime.datetime.strptime(item["updated_at"], dateformat) if extended else None,
        )

    def __embed_for_slug(self, slug: str) -> str:
        res = self.__website_request(f"/videos/{slug}")
        embed_info = re.search(EMBED_FINDER, res.text)
        if embed_info is None:
            msg = f"could not find embed url for {slug}"
            raise ValueError(msg)
        return html.unescape(embed_info.group(1))

    def __config_from_embed(self, url: str) -> dict:
        embed_page = requests.get(
            url,
            headers={
                "Referer": self.REFERER_URL,
            },
            timeout=REQUEST_TIMEOUT_S,
        )
        config_info = re.search(CONFIG_FINDER, embed_page.text)
        if config_info is None:
            msg = f"could not find config url in {url} ({embed_page}/{embed_page.text})"
            raise ValueError(msg)
        config_url = json.loads(config_info.group(1))["config_url"]
        return requests.get(config_url, timeout=REQUEST_TIMEOUT_S).json()

    def playable_from_id(self, pid: int) -> tuple[Playable, VideoData]:
        video_res = self.__get_video_by_id(pid)
        embed = self.__embed_for_slug(video_res["url"])
        return self.__playable_from_id(pid, embed, video_res)

    def playable_from_slug(self, slug: str) -> tuple[Playable, VideoData]:
        embed = self.__embed_for_slug(slug)
        id_info = re.search(EMBED_ID_FINDER, embed)
        if id_info is None:
            msg = f"could not find id in {embed}"
            raise ValueError(msg)
        pid = int(id_info.group(1))
        log_message(f"video {pid} from {slug}", level=LOGDEBUG)
        return self.__playable_from_id(pid, embed)

    def __get_video_by_id(self, vid: int) -> dict:
        video_res = self.__api_request(f"/videos/{vid}", use_tv=True)
        if video_res is None:
            msg = f"could not find video {vid}"
            raise ValueError(msg)
        log_message(f"video {vid}: {video_res}", level=LOGDEBUG)
        return video_res

    def __playable_from_id(self, pid: int, embed: str, video_res: dict | None = None) -> tuple[Playable, VideoData]:
        config = self.__config_from_embed(embed)
        log_message(f"config for {pid}: {config}", level=LOGDEBUG)
        if video_res is None:
            video_res = self.__get_video_by_id(pid)

        subtitles_raw = video_res.get("tracks", {}).get("subtitles", [])
        subtitles = []
        for sub in subtitles_raw:
            links = sub.get("_links", [])
            for fmt in ("vtt", "srt"):
                fmt_data = links.get(fmt)
                if fmt_data is None:
                    continue
                subtitles.append(fmt_data["href"])
        playable = self.__parse_playable(video_res, embedded=True)
        formats = config.get("request", {}).get("files", {})
        if "dash" in formats and False:  # noqa: SIM223
            # Kodi supports it but the format sent back is some homebrew JSON instead of a MPD file
            fmt = formats["dash"]
            log_message(f"using dash format for playback {fmt}", level=LOGDEBUG)
            cdn = self.__get_best_cdn(fmt)
            data = VideoData(
                url=cdn["url"],
                subtitles=subtitles,
                mime_type="application/dash+xml",
            )
        elif "hls" in formats:
            fmt = formats["hls"]
            log_message(f"using HLS format for playback {fmt}", level=LOGDEBUG)
            cdn = self.__get_best_cdn(fmt)
            data = VideoData(
                url=cdn["url"],
                subtitles=subtitles,
                mime_type="application/vnd.apple.mpegurl",
            )
        else:
            msg = f"could not find playable format for {pid}"
            raise ValueError(msg)
        return playable, data

    def __get_best_cdn(self, fmt: dict) -> dict:
        def_cdn = fmt.get("default_cdn")
        cdns = fmt.get("cdns", {})
        if len(cdns) == 0:
            msg = "could not find any cdns"
            raise ValueError(msg)
        if def_cdn is None or def_cdn not in cdns:
            def_cdn = next(iter(cdns.keys()))
        return cdns[def_cdn]


art_dimensions = {
    "poster": (1000, 1500),  # 2:3
    "fanart": (1920, 1080),  # 16:9
    "thumb": (1280, 720),  # 16:9
    "banner": (1000, 185),  # 5.4:1
    "landscape": (1280, 720),  # 16:9
}


def thumbnail_formatter(src: str, *, art: str, blurred: bool = False) -> str:
    args = {}
    if blurred:
        args["blur"] = 180
    if art in art_dimensions:
        args["w"], args["h"] = art_dimensions[art]
        args["fit"] = "crop"
    return f"{src}?{urlencode(args)}"
