import datetime

import xbmc
import xbmcgui

from .addon import Addon
from .config import PlayState
from .utils import log_exception, log_message


class MonitorPlayer(xbmc.Player):
    def __init__(self) -> None:
        super().__init__()
        self.monitor = xbmc.Monitor()
        self.playing = None

    def __update_play_state(self, completed: bool = False) -> None:
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
            last_seen=datetime.datetime.now(),
        )
        Addon.CONFIG.set_playstate(self.playing, ps)
        log_message(f"Updated play state for video {self.playing}: {ps}")

    def onPlayBackStarted(self) -> None:
        li: xbmcgui.ListItem = self.getPlayingItem()
        video_id = li.getProperty(Addon.PLAYER_VIDEO_ID)
        if video_id is None or video_id == "":
            log_message("No video ID found, cannot update play state")
            return
        self.playing = int(video_id)
        log_message(f"Playback started: {self.playing}")

    def onPlayBackPaused(self) -> None:
        self.__update_play_state()
        log_message("Playback paused")

    def onPlayBackStopped(self) -> None:
        self.__update_play_state()
        self.playing = None
        log_message("Playback stopped")

    def onPlayBackEnded(self) -> None:
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
