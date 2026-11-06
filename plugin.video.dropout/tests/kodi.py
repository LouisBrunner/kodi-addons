from collections.abc import Sequence

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from .double import Module


class Kodi:
    def __init__(self) -> None:
        self.xbmc = Module(xbmc)
        self.gui = Module(xbmcgui)
        self.addonm = Module(xbmcaddon)
        self.plugin = Module(xbmcplugin)
        self.vfs = Module(xbmcvfs)
        self.dialog = self.gui.sub_double(xbmcgui.Dialog)
        self.player = self.xbmc.sub_double(xbmc.Player)
        self.monitor = self.xbmc.sub_double(xbmc.Monitor)
        self.addon = self.addonm.sub_double(xbmcaddon.Addon)
        self.settings = self.addonm.sub_double(xbmcaddon.Settings)
        self.ListItem = self.gui.sub_pod(xbmcgui.ListItem)

    def is_playing(self, *, answer: bool) -> None:
        self.player.expect(self.player._.isPlaying).returns(answer)

    def stops_playback(self) -> None:
        self.player.expect(self.player._.stop).returns(None)

    def gets_setting_string(self, key: str, value: str) -> None:
        self.settings.expect(self.settings._.getString, key).returns(value)

    def sets_setting(self, key: str, value: str) -> None:
        self.addon.expect(self.addon._.setSetting, key, value).returns(None)

    def runs(self, command: str) -> None:
        self.xbmc.expect(self.xbmc._.executebuiltin, command).returns(None)

    def refreshes(self) -> None:
        self.runs("Container.Refresh")

    def notifies(self, addon: str, message: str, time: int, icon: str) -> None:
        self.runs(f"Notification({addon!r}, {message!r}, {time}, {icon!r})")

    def logs(self, level: int, message: str) -> None:
        self.xbmc.expect(self.xbmc._.log, message, level).returns(None)

    def logs_warning(self, message: str) -> None:
        self.logs(xbmc.LOGWARNING, f"plugin.video.dropout: {message}")

    def logs_error(self, message: str) -> None:
        self.logs(xbmc.LOGERROR, f"plugin.video.dropout: {message}")

    def inputs_dialog(self, title: str, typed: str, *, defaults: str = "", typ: int = 0, option: int = 0) -> None:
        self.dialog.expect(self.dialog._.input, title, defaults, type=typ, option=option).returns(typed)

    def okays_dialog(self, title: str, message: str, *, confirmed: bool) -> None:
        self.dialog.expect(self.dialog._.ok, title, message).returns(confirmed)

    def opens_settings(self) -> None:
        self.addon.expect(self.addon._.openSettings).returns(None)

    def selects_dialog(
        self,
        title: str,
        items: Sequence[str | xbmcgui.ListItem],
        answer: int,
        *,
        preselect: int = 0,
        use_details: bool = False,
    ) -> None:
        self.dialog.expect(self.dialog._.select, title, items, preselect=preselect, useDetails=use_details).returns(
            answer
        )
