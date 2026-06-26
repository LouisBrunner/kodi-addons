import datetime
from typing import TYPE_CHECKING

import xbmc

from .addon import Addon
from .config import PlayState
from .utils import log_exception, log_message

if TYPE_CHECKING:
    import xbmcgui


class MonitorPlayer(xbmc.Player):
    def __init__(self) -> None:
        super().__init__()
        self.monitor = xbmc.Monitor()
        self.playing = None

    def __update_play_state(self, *, completed: bool = False) -> None:
        if self.playing is None:
            return
        try:
            pos = int(self.getTime())
        except RuntimeError:
            log_exception("Error getting playback time")
            pos = 0
        ps = PlayState(
            completed=completed,
            timecode=0,
            duration_s=pos,
            last_seen=datetime.datetime.now(tz=datetime.UTC),
        )
        Addon.CONFIG.set_playstate(self.playing, ps)
        log_message(f"Updated play state for video {self.playing}: {ps}")

    # @override
    def onPlayBackStarted(self) -> None:  # noqa: N802
        li: xbmcgui.ListItem = self.getPlayingItem()
        video_id = li.getProperty(Addon.PLAYER_VIDEO_ID)
        if video_id is None or video_id == "":
            log_message("No video ID found, cannot update play state")
            return
        self.playing = int(video_id)
        log_message(f"Playback started: {self.playing}")

    # @override
    def onPlayBackPaused(self) -> None:  # noqa: N802
        self.__update_play_state()
        log_message("Playback paused")

    # @override
    def onPlayBackStopped(self) -> None:  # noqa: N802
        self.__update_play_state()
        self.playing = None
        log_message("Playback stopped")

    # @override
    def onPlayBackEnded(self) -> None:  # noqa: N802
        self.__update_play_state(completed=True)
        self.playing = None
        log_message("Playback ended")

    def loop(self) -> None:
        while not self.monitor.abortRequested():
            if self.playing is not None:
                self.__update_play_state()
            if self.monitor.waitForAbort(5):
                break


def start_monitor() -> None:
    log_message("Starting player monitor")
    MonitorPlayer().loop()
