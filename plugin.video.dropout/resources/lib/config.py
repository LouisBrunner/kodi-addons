import datetime
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class PlayState:
    completed: bool
    duration_s: int
    timecode: int
    last_seen: datetime.datetime
    from_us: bool = False


@dataclass
class Search:
    search: str
    first: datetime.datetime


@dataclass
class Credentials:
    hash: str
    token: str
    user_id: int
    when: datetime.datetime


class Config:
    _COOKIEJAR_FILE = "cookiejar.json"
    _CREDENTIALS_FILE = "credentials.json"
    _PLAYSTATE_FILE = "playstate.json"
    _SEARCHES_FILE = "searches.json"

    _MAX_SEARCHES = 15

    def __init__(self, path: str) -> None:
        self.__path = path

    def get_cookie_jar(self) -> dict:
        return self.__read_json_file(self._COOKIEJAR_FILE, dfault={})

    def set_cookie_jar(self, cookiejar: dict) -> None:
        self.__write_json_file(self._COOKIEJAR_FILE, cookiejar)

    def get_playstates(self) -> Dict[int, PlayState]:
        playstates = self.__read_json_file(self._PLAYSTATE_FILE, dfault={})
        return {
            int(k): PlayState(
                completed=v["completed"],
                duration_s=v["duration_s"],
                timecode=v["timecode"],
                last_seen=datetime.datetime.fromisoformat(v["last_seen"]),
                from_us=True,
            )
            for k, v in playstates.items()
        }

    def get_playstate(self, video_id: int) -> Optional[PlayState]:
        playstates = self.__read_json_file(self._PLAYSTATE_FILE, dfault={})
        if str(video_id) not in playstates:
            return None
        data = playstates[str(video_id)]
        return PlayState(
            completed=data["completed"],
            duration_s=data["duration_s"],
            timecode=data["timecode"],
            last_seen=datetime.datetime.fromisoformat(data["last_seen"]),
            from_us=True,
        )

    def set_playstate(self, video_id: int, playstate: PlayState) -> None:
        playstate_data = {
            "completed": playstate.completed,
            "duration_s": playstate.duration_s,
            "timecode": playstate.timecode,
            "last_seen": playstate.last_seen.isoformat(),
        }
        current_playstate = self.__read_json_file(self._PLAYSTATE_FILE, dfault={})
        current_playstate[str(video_id)] = playstate_data
        self.__write_json_file(self._PLAYSTATE_FILE, current_playstate)

    def get_searches(self) -> List[Search]:
        searches = self.__read_json_file(self._SEARCHES_FILE, dfault={})
        res = searches.get("searches", [])
        return [
            Search(
                search=s["search"],
                first=datetime.datetime.fromisoformat(s["first"]),
            )
            for s in res
        ]

    def add_search(self, search: str) -> None:
        searches = self.__read_json_file(self._SEARCHES_FILE, dfault={})
        searches["searches"] = searches.get("searches", [])
        if search not in searches["searches"]:
            searches["searches"].append(
                {
                    "search": search,
                    "first": datetime.datetime.now().isoformat(),
                }
            )
            if len(searches["searches"]) > self._MAX_SEARCHES:
                searches["searches"].pop(0)
        self.__write_json_file(self._SEARCHES_FILE, searches)

    def remove_search(self, search: str) -> None:
        searches = self.__read_json_file(self._SEARCHES_FILE, dfault={})
        searches["searches"] = searches.get("searches", [])
        searches["searches"] = list(
            filter(lambda s: s["search"] != search, searches["searches"])
        )
        self.__write_json_file(self._SEARCHES_FILE, searches)

    def get_credentials(self) -> Optional[Credentials]:
        credentials = self.__read_json_file(self._CREDENTIALS_FILE, dfault={})
        if not credentials:
            return None
        return Credentials(
            hash=credentials["hash"],
            token=credentials["token"],
            user_id=credentials["user_id"],
            when=datetime.datetime.fromisoformat(credentials["when"]),
        )

    def set_credentials(self, credentials: Optional[Credentials]) -> None:
        if credentials is None:
            os.remove(self.__get_path(self._CREDENTIALS_FILE))
            return
        credentials_data = {
            "hash": credentials.hash,
            "token": credentials.token,
            "user_id": credentials.user_id,
            "when": credentials.when.isoformat(),
        }
        self.__write_json_file(self._CREDENTIALS_FILE, credentials_data)

    def __get_path(self, file: str) -> str:
        return os.path.join(self.__path, file)

    def __read_json_file(self, file: str, dfault: dict) -> dict:
        path = self.__get_path(file)

        if not os.path.exists(path):
            return dfault

        with open(path, "r") as f:
            return json.load(f)

    def __write_json_file(self, file: str, data: dict) -> None:
        path = self.__get_path(file)

        with open(path, "w") as f:
            json.dump(data, f)
