import datetime
import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self, TypeVar, cast

from requests.cookies import RequestsCookieJar, create_cookie
from typing_extensions import override

_JSON = dict[str, "_JSON"] | list["_JSON"] | str | int | float | bool | None
_JSON_DICT = dict[str, Any]


class _Serial(ABC):
    @classmethod
    def unpack(cls, data: _JSON) -> Self | None:
        if not isinstance(data, dict):
            return None
        return cast(
            "Self",
            cls.from_dict(cast("_JSON_DICT", data)),
        )

    @classmethod
    @abstractmethod
    def from_dict(cls, data: _JSON_DICT) -> "_Serial": ...

    @abstractmethod
    def to_dict(self) -> _JSON: ...


@dataclass
class PlayState(_Serial):
    completed: bool
    duration_s: int
    timecode: int
    last_seen: datetime.datetime
    from_us: bool = False

    @classmethod
    @override
    def from_dict(cls, data: _JSON_DICT) -> "PlayState":
        return cls(
            completed=data["completed"],
            duration_s=data["duration_s"],
            timecode=data["timecode"],
            last_seen=cls.__parse_last_seen(data["last_seen"]),
            from_us=True,
        )

    @override
    def to_dict(self) -> _JSON:
        return {
            "completed": self.completed,
            "duration_s": self.duration_s,
            "timecode": self.timecode,
            "last_seen": self.last_seen.isoformat(),
        }

    @staticmethod
    def __parse_last_seen(last_seen: str) -> datetime.datetime:
        parsed = datetime.datetime.fromisoformat(last_seen)
        if parsed.tzinfo is None:
            # legacy entries were stored without a timezone, assume UTC (as newer ones are)
            parsed = parsed.replace(tzinfo=datetime.UTC)
        return parsed


class PlayStates(dict[int, PlayState], _Serial):
    @classmethod
    @override
    def from_dict(cls, data: _JSON_DICT) -> "PlayStates":
        return cls({int(k): PlayState.from_dict(v) for k, v in data.items()})

    @override
    def to_dict(self) -> _JSON:
        return {str(k): v.to_dict() for k, v in self.items()}


@dataclass
class Search(_Serial):
    search: str
    first: datetime.datetime

    @classmethod
    @override
    def from_dict(cls, data: _JSON_DICT) -> "Search":
        return cls(
            search=data["search"],
            first=datetime.datetime.fromisoformat(data["first"]),
        )

    @override
    def to_dict(self) -> _JSON:
        return {
            "search": self.search,
            "first": self.first.isoformat(),
        }


@dataclass
class Searches(_Serial):
    searches: list[Search]

    @classmethod
    @override
    def from_dict(cls, data: _JSON_DICT) -> "Searches":
        return cls(
            searches=[Search.from_dict(s) for s in data.get("searches", [])],
        )

    @override
    def to_dict(self) -> _JSON:
        return {
            "searches": [s.to_dict() for s in self.searches],
        }


@dataclass
class Profile(_Serial):
    index: str
    name: str
    pin_locked: bool
    image: str

    @classmethod
    @override
    def from_dict(cls, data: _JSON_DICT) -> "Profile":
        return cls(
            index=data["index"],
            name=data["name"],
            pin_locked=data["pin_locked"],
            image=data["image"],
        )

    @override
    def to_dict(self) -> _JSON:
        return {
            "index": self.index,
            "name": self.name,
            "pin_locked": self.pin_locked,
            "image": self.image,
        }


@dataclass
class Credentials(_Serial):
    hash: str
    token: str
    user_id: int
    when: datetime.datetime
    profiles: list[Profile]
    selected_profile: str | None = None
    pins: dict[str, str] = field(default_factory=dict)

    @classmethod
    @override
    def from_dict(cls, data: _JSON_DICT) -> "Credentials":
        return cls(
            hash=data["hash"],
            token=data["token"],
            user_id=data["user_id"],
            when=datetime.datetime.fromisoformat(data["when"]),
            profiles=[Profile.from_dict(p) for p in data.get("profiles", [])],
            selected_profile=data.get("selected_profile"),
            pins=data.get("pins", {}),
        )

    @override
    def to_dict(self) -> _JSON:
        return {
            "hash": self.hash,
            "token": self.token,
            "user_id": self.user_id,
            "when": self.when.isoformat(),
            "profiles": [p.to_dict() for p in self.profiles],
            "selected_profile": self.selected_profile,
            "pins": self.pins,
        }


@dataclass
class Watchlist(_Serial):
    ids: list[int]
    when: datetime.datetime

    @classmethod
    @override
    def from_dict(cls, data: _JSON_DICT) -> "Watchlist":
        return cls(
            ids=data["ids"],
            when=datetime.datetime.fromisoformat(data["when"]),
        )

    @override
    def to_dict(self) -> _JSON:
        return {
            "ids": self.ids,
            "when": self.when.isoformat(),
        }


class CookieJar(RequestsCookieJar, _Serial):  # ty: ignore[invalid-method-override]
    def __init__(self, cookiejar: RequestsCookieJar | None = None) -> None:
        super().__init__()
        if cookiejar is not None:
            self.update(cookiejar)

    @classmethod
    @override
    def from_dict(cls, data: _JSON_DICT) -> "CookieJar":
        jar = cls()
        entries = data.get("cookies")
        for entry in entries if isinstance(entries, list) else []:
            expires = entry.get("expires")
            if expires is not None and expires <= time.time():
                continue
            jar.set_cookie(
                create_cookie(
                    entry["name"],
                    entry["value"],
                    domain=entry["domain"],
                    path=entry["path"],
                    secure=entry.get("secure", False),
                    expires=expires,
                )
            )
        return jar

    @override
    def to_dict(self) -> _JSON:
        return {
            "cookies": [
                {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path,
                    "secure": c.secure,
                    "expires": c.expires,
                }
                for c in self
            ]
        }


class Config:
    _COOKIEJAR_FILE = "cookiejar.json"
    _CREDENTIALS_FILE = "credentials.json"

    _PLAYSTATE_FILE = "playstate.json"
    _SEARCHES_FILE = "searches.json"
    _WATCHLIST_FILE = "watchlist.json"
    _PER_PROFILE_FILES = (_PLAYSTATE_FILE, _SEARCHES_FILE, _WATCHLIST_FILE)

    _MAX_SEARCHES = 15

    def __init__(self, path: str) -> None:
        self.__path = Path(path)

        for file in self._PER_PROFILE_FILES:
            legacy = self.__make_path(file)
            target = self.__make_path(file, profile="0")
            if legacy.exists():
                if not target.exists():
                    legacy.rename(target)
                else:
                    legacy.unlink()

    def get_cookie_jar(self) -> RequestsCookieJar | None:
        return self.__read_file(CookieJar, self._COOKIEJAR_FILE)

    def set_cookie_jar(self, cookiejar: RequestsCookieJar | None) -> None:
        return self.__write_file(self._COOKIEJAR_FILE, CookieJar(cookiejar) if cookiejar is not None else None)

    def get_playstates(self) -> PlayStates:
        return self.__read_file(PlayStates, self._PLAYSTATE_FILE, profile="") or PlayStates()

    def get_playstate(self, video_id: int) -> PlayState | None:
        playstates = self.__read_file(PlayStates, self._PLAYSTATE_FILE, profile="")
        if playstates is None or video_id not in playstates:
            return None
        return playstates[video_id]

    def set_playstate(self, video_id: int, playstate: PlayState) -> None:
        def _mutate(playstates: PlayStates) -> PlayStates:
            playstates[video_id] = playstate
            return playstates

        return self.__update_file(PlayStates, self._PLAYSTATE_FILE, _mutate, profile="")

    def get_searches(self) -> list[Search]:
        res = self.__read_file(Searches, self._SEARCHES_FILE, profile="")
        if res is None:
            return []
        return res.searches

    def add_search(self, search: str) -> None:
        def _mutate(searches: Searches) -> Searches:
            if search in searches.searches:
                return searches

            searches.searches.append(
                Search(
                    search=search,
                    first=datetime.datetime.now(tz=datetime.UTC),
                )
            )
            if len(searches.searches) > self._MAX_SEARCHES:
                searches.searches.pop(0)
            return searches

        self.__update_file(Searches, self._SEARCHES_FILE, _mutate, profile="")

    def remove_search(self, search: str) -> None:
        def _mutate(searches: Searches) -> Searches:
            searches.searches = [s for s in searches.searches if s.search != search]
            return searches

        return self.__update_file(Searches, self._SEARCHES_FILE, _mutate, profile="")

    def clear_data(self, *, cookies: bool = True) -> None:
        for file in self.__path.iterdir():
            if (
                file.name.endswith(self._SEARCHES_FILE)
                or file.name.endswith(self._PLAYSTATE_FILE)
                or file.name.endswith(self._WATCHLIST_FILE)
                or file.name.endswith(self._CREDENTIALS_FILE)
                or (file.name.endswith(self._COOKIEJAR_FILE) and cookies)
            ):
                file.unlink()

    def get_credentials(self) -> Credentials | None:
        return self.__read_file(Credentials, self._CREDENTIALS_FILE)

    def set_credentials(self, credentials: Credentials | None) -> None:
        return self.__write_file(self._CREDENTIALS_FILE, credentials)

    def get_watchlist(self) -> Watchlist | None:
        return self.__read_file(Watchlist, self._WATCHLIST_FILE)

    def set_watchlist(self, watchlist: Watchlist | None) -> None:
        return self.__write_file(self._WATCHLIST_FILE, watchlist)

    def __update_credentials(self, fn: Callable[[Credentials], Credentials]) -> None:
        return self.__update_file(Credentials, self._CREDENTIALS_FILE, fn)

    def get_profile(self) -> str | None:
        creds = self.get_credentials()
        if creds is None:
            return None
        return creds.selected_profile

    def set_profile(self, index: str, *, token: str) -> None:
        def _mutate(creds: Credentials) -> Credentials:
            creds.selected_profile = index
            creds.token = token
            return creds

        return self.__update_credentials(_mutate)

    def get_pin(self, index: str) -> str | None:
        creds = self.get_credentials()
        if creds is None:
            return None
        return creds.pins.get(index)

    def set_pin(self, index: str, pin: str | None) -> None:
        def _mutate(creds: Credentials) -> Credentials:
            if pin is None:
                creds.pins.pop(index, None)
            else:
                creds.pins[index] = pin
            return creds

        return self.__update_credentials(_mutate)

    @staticmethod
    def __prefixed(file: str, index: str) -> str:
        return f"profile{index}_{file}"

    def __global_path(self, file: str) -> Path:
        return self.__path / file

    def __make_path(self, file: str, *, profile: str | None = None) -> Path:
        if profile is not None:
            if profile == "":
                profile = self.get_profile()
            if profile is None:
                msg = "No profile selected"
                raise ValueError(msg)
            file = self.__prefixed(file, profile)
        return self.__global_path(file)

    T = TypeVar("T", bound=_Serial)

    def __read_file(self, kind: type[T], file: str, *, profile: str | None = None) -> T | None:
        path = self.__make_path(file, profile=profile)
        res = self.__read_json_file(path)
        if res is None:
            return None
        return kind.unpack(res)

    def __read_json_file(self, path: Path) -> _JSON | None:
        if not path.exists():
            return None

        with path.open() as f:
            return json.load(f)

    def __write_file(self, file: str, data: T | None, *, profile: str | None = None) -> None:
        path = self.__make_path(file, profile=profile)
        if data is None:
            path.unlink(missing_ok=True)
            return
        self.__write_json_file(path, data.to_dict())

    def __write_json_file(self, path: Path, data: _JSON) -> None:
        with path.open("w") as f:
            json.dump(data, f)

    def __update_file(self, kind: type[T], file: str, fn: Callable[[T], T], *, profile: str | None = None) -> None:
        path = self.__make_path(file, profile=profile)
        raw = self.__read_json_file(path)
        if raw is None:
            raw = {}
        current = kind.unpack(raw)
        if current is None:
            return
        updated = fn(current)
        self.__write_json_file(path, updated.to_dict())
