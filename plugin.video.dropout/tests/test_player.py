from collections.abc import Iterable
from typing import Literal

import pytest

from resources.lib.config import PlayState, PlayStates

from .common import NOW
from .plugin import Plugin

_Action = float | tuple[int | None, float] | Literal["resume", "pause", "stop", "idle", "end"]


class Viewer:
    def __init__(self, plugin: Plugin) -> None:
        self.plugin = plugin
        self.kodi = plugin.kodi

    def starts(self, flow: Iterable[_Action]) -> PlayStates:  # noqa: C901
        actions = iter(flow)

        abort = False
        pos: float | None = None
        item = self.kodi.ListItem()

        def _harness() -> bool:
            nonlocal abort, pos, item
            action: float | tuple[int | None, float] | Literal["resume", "pause", "stop", "idle", "end"] | None = next(
                actions, None
            )
            if action is None:
                abort = True
                return True
            if isinstance(action, float | int):
                pos = float(action)
            elif isinstance(action, tuple):
                video, pos = action
                item = self.kodi.ListItem()
                if video is not None:
                    item.setProperty("plugin.video.dropout.video_id", str(video))
                self.kodi.player.real.onPlayBackStarted()
            else:
                match action:
                    case "resume":
                        pass
                    case "pause":
                        pass
                    case "stop":
                        pos = None
                        item = None
                        self.kodi.player.real.onPlayBackStopped()
                    case "end":
                        pos = None
                        item = None
                        self.kodi.player.real.onPlayBackEnded()
            return False

        def _get_time() -> float:
            if pos is not None:
                return pos
            raise RuntimeError(...)

        self.kodi.player.mock.getPlayingItem.side_effect = lambda: item if pos is not None else None
        self.kodi.player.mock.isPlaying.side_effect = lambda: pos is not None
        self.kodi.player.mock.getTime.side_effect = _get_time
        self.kodi.monitor.mock.abortRequested.side_effect = _harness
        self.kodi.monitor.mock.waitForAbort.side_effect = lambda _: abort

        from resources.lib.player import MonitorPlayer  # noqa: PLC0415

        MonitorPlayer.start()

        return self.plugin.storage().get_playstates()


pytestmark = pytest.mark.usefixtures("signed_in")


def _progress(position: int, *, completed: bool = False) -> PlayState:
    return PlayState(completed=completed, duration_s=position, timecode=0, last_seen=NOW, from_us=True)


@pytest.fixture
def viewer(plugin: Plugin) -> Viewer:
    return Viewer(plugin)


def test_pausing_a_video(viewer: Viewer) -> None:
    flow: list[_Action] = ["idle", (7, 0), "idle", "idle", 42, 42.5, "pause", "idle"]
    assert viewer.starts(flow) == {7: _progress(42)}


def test_stopping_a_paused_video(viewer: Viewer) -> None:
    flow: list[_Action] = [(10, 10), 11, "idle", 44, "pause", "idle", "stop"]
    assert viewer.starts(flow) == {10: _progress(44)}


def test_stopping_a_video(viewer: Viewer) -> None:
    flow: list[_Action] = [(12, 10), 10, "idle", 25, "stop", "idle", "idle", "idle", "idle"]
    assert viewer.starts(flow) == {12: _progress(25)}


def test_finishing_a_video(viewer: Viewer) -> None:
    flow: list[_Action] = [(42, 3600.23), "idle", 4000, 5000, 6000, 3000, "idle", 7000, "end", "idle"]
    assert viewer.starts(flow) == {42: _progress(7000, completed=True)}


def test_coming_back_to_a_video(viewer: Viewer) -> None:
    flow: list[_Action] = [(7, 0), 500, "stop", "idle", (7, 500), 800, 1500, "end"]
    assert viewer.starts(flow) == {7: _progress(1500, completed=True)}


def test_autoplay_behavior(viewer: Viewer) -> None:
    flow: list[_Action] = [(7, 0), 1000, "end", (8, 0), 20, "pause", "idle"]
    assert viewer.starts(flow) == {7: _progress(1000, completed=True), 8: _progress(20)}


def test_progress_is_saved_while_watching(viewer: Viewer) -> None:
    flow: list[_Action] = [(7, 0), 30, "idle", 32, "idle"]
    assert viewer.starts(flow) == {7: _progress(32)}


def test_different_videos_are_independent(viewer: Viewer) -> None:
    flow: list[_Action] = [(7, 80), "pause", "stop", (8, 0), "stop"]
    assert viewer.starts(flow) == {7: _progress(80), 8: _progress(0)}


def test_other_addons_are_not_recorded(viewer: Viewer) -> None:
    flow: list[_Action] = ["idle", (None, 0), 10, "pause", "resume", 600, "stop", "idle", (None, 5), "end"]
    assert viewer.starts(flow) == {}


def test_other_addons_do_not_overwrite(viewer: Viewer) -> None:
    flow: list[_Action] = [(7, 0), 30, "pause", (None, 500), "pause", "stop"]
    assert viewer.starts(flow) == {7: _progress(30)}


def test_an_evening_of_television(viewer: Viewer) -> None:
    flow: list[_Action] = [
        (7, 0),
        600,
        "pause",
        "resume",
        900,
        "stop",
        (None, 0),
        60,
        "pause",
        "resume",
        "end",
        (8, 0),
        1200,
        2400,
        "end",
    ]
    assert viewer.starts(flow) == {7: _progress(900), 8: _progress(2400, completed=True)}
