import datetime
from typing import TYPE_CHECKING

import xbmc
from typing_extensions import override

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
        self.last_pos = 0

    def __update_play_state(self, *, completed: bool = False) -> None:
        if self.playing is None:
            return
        if self.isPlaying():
            try:
                self.last_pos = int(self.getTime())
            except RuntimeError:
                log_exception("Error getting playback time")
        ps = PlayState(
            completed=completed,
            timecode=0,
            duration_s=self.last_pos,
            last_seen=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        Addon.CONFIG.set_playstate(self.playing, ps)
        log_message(f"Updated play state for video {self.playing}: {ps}")

    @override
    def onPlayBackStarted(self) -> None:
        li: xbmcgui.ListItem = self.getPlayingItem()
        video_id = li.getProperty(Addon.PLAYER_VIDEO_ID)
        if video_id is None or video_id == "":
            log_message("No video ID found, cannot update play state")
            self.playing = None
            return
        self.playing = int(video_id)
        self.last_pos = 0
        log_message(f"Playback started: {self.playing}")

    @override
    def onPlayBackStopped(self) -> None:
        self.__update_play_state()
        self.playing = None
        self.last_pos = 0
        log_message("Playback stopped")

    @override
    def onPlayBackEnded(self) -> None:
        self.__update_play_state(completed=True)
        self.playing = None
        self.last_pos = 0
        log_message("Playback ended")

    def loop(self) -> None:
        while not self.monitor.abortRequested():
            if self.playing is not None:
                self.__update_play_state()
            if self.monitor.waitForAbort(5):
                break

    @classmethod
    def start(cls) -> None:
        log_message("Starting player monitor")
        cls().loop()
