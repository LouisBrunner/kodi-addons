# FIXME(3.9): drop in 3.10/11
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from urllib.parse import urlencode

from resources.lib.config import Config

from .dropout import Dropout
from .kodi import Kodi


class Plugin:
    def __init__(self, kodi: Kodi, dropout: Dropout, data_dir: Path, addon_dir: Path) -> None:
        self.kodi = kodi
        self.dropout = dropout
        self.data_dir = data_dir
        self.addon_dir = addon_dir

    def load(self, module: str) -> ModuleType:
        for name in [
            name for name in sys.modules if name.startswith("resources.lib.") and name != "resources.lib.config"
        ]:
            del sys.modules[name]
        return importlib.import_module(f"resources.lib.{module}")

    def storage(self) -> Config:
        return self.load("config").Config(str(self.data_dir))

    def has_legacy_cookies(self, **cookies: str) -> None:
        (self.data_dir / "cookiejar.json").write_text(json.dumps(cookies))

    def visit(self, action: str | None = None, **params: str) -> None:
        query = urlencode({**params, **({"action": action} if action else {})})
        self.kodi.addon.expect(self.kodi.addon._.getAddonInfo, "path").returns(str(self.addon_dir))
        self.kodi.vfs.expect(
            self.kodi.vfs._.translatePath, "special://profile/addon_data/plugin.video.dropout"
        ).returns(self.data_dir)
        self.kodi.xbmc.expect(self.kodi.xbmc._.getRegion, "datelong").returns("%B %d, %Y")
        self.load("plugin").dispatch(["plugin://plugin.video.dropout", "1337", f"?{query}"])
