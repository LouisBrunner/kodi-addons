import datetime as dt
from collections.abc import Generator, Iterator
from pathlib import Path

import pytest
import responses
import xbmcgui
from responses.registries import OrderedRegistry
from time_machine import TimeMachineFixture
from xbmc import LOGDEBUG, LOGINFO

from tests.test_strings import load_strings

from .common import NOW, Settings
from .double import Double
from .dropout import Dropout
from .kodi import Kodi
from .plugin import Plugin


@pytest.fixture(autouse=True)
def frozen_time(time_machine: TimeMachineFixture) -> None:
    time_machine.move_to(NOW, tick=False)


@pytest.fixture(autouse=True)
def double_checks() -> Generator[None, None, None]:
    Double.reset()
    yield
    Double.ensure()


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "addon_data"
    folder.mkdir()
    return folder


@pytest.fixture
def addon_dir() -> Path:
    return Path(__file__).parents[2]


@pytest.fixture
def kodi() -> Kodi:
    return Kodi()


@pytest.fixture
def dropout() -> Iterator[Dropout]:
    with responses.RequestsMock(assert_all_requests_are_fired=True, registry=OrderedRegistry) as http:
        yield Dropout(http)


@pytest.fixture
def plugin(kodi: Kodi, dropout: Dropout, data_dir: Path, addon_dir: Path) -> Plugin:
    kodi.addon.handle(kodi.addon._.getSettings, lambda: (True, kodi.settings), quiet=True)
    kodi.settings.handle(kodi.settings._.getBool, lambda name: (name == "debug_mode", None), quiet=True)

    def _ignore_logs(_: str, level: int) -> tuple[bool, None]:
        return (level in [LOGDEBUG, LOGINFO], None)

    kodi.xbmc.handle(kodi.xbmc._.log, _ignore_logs, quiet=True)

    str_builtins, str_addons = load_strings()

    def _localize(strs: dict[int, str], strid: int) -> tuple[bool, str]:
        return (True, f"_{strs.get(strid, str(strid))}")

    kodi.addon.handle(kodi.addon._.getLocalizedString, lambda strid: _localize(str_addons, strid))
    kodi.xbmc.handle(kodi.xbmc._.getLocalizedString, lambda strid: _localize(str_builtins, strid))

    return Plugin(kodi, dropout, data_dir, addon_dir)


Profiles = tuple[list[Dropout.Profile], list[xbmcgui.ListItem]]


@pytest.fixture
def test_profiles(kodi: Kodi) -> Profiles:
    return (
        [
            Dropout.Profile(index=0, name="Brennan", pin_locked=False, image="https://images.example.test/brennan.jpg"),
            Dropout.Profile(index=1, name="Murph", pin_locked=True, image="https://images.example.test/murph.jpg"),
            Dropout.Profile(index=2, name="Emily", pin_locked=False, image="https://images.example.test/axford.jpg"),
        ],
        [
            kodi.ListItem.expected(
                label="Brennan",
                art={
                    "thumb": "https://images.example.test/brennan.jpg",
                    "icon": "https://images.example.test/brennan.jpg",
                },
            ),
            kodi.ListItem.expected(
                label="_Murph (PIN)",
                art={
                    "thumb": "https://images.example.test/murph.jpg",
                    "icon": "https://images.example.test/murph.jpg",
                },
            ),
            kodi.ListItem.expected(
                label="Emily",
                art={
                    "thumb": "https://images.example.test/axford.jpg",
                    "icon": "https://images.example.test/axford.jpg",
                },
            ),
        ],
    )


@pytest.fixture
def test_settings() -> Settings:
    return Settings(email="brennan@d20.dropout", password="copperkettle111")


def add_settings(kodi: Kodi, test_settings: Settings) -> Settings:
    kodi.gets_setting_string("username", test_settings.email)
    kodi.gets_setting_string("password", test_settings.password)
    return test_settings


@pytest.fixture
def with_settings(kodi: Kodi, test_settings: Settings) -> Settings:
    return add_settings(kodi, test_settings)


FolderAction = tuple[str, xbmcgui.ListItem, bool]

AddonArt = {
    "icon": str(Path(__file__).parents[2] / "icon.png"),
    "thumb": str(Path(__file__).parents[2] / "fanart.png"),
    "fanart": str(Path(__file__).parents[2] / "fanart.png"),
    "landscape": str(Path(__file__).parents[2] / "fanart.png"),
    "poster": str(Path(__file__).parents[2] / "poster.png"),
}


def make_view(kodi: Kodi, title: str, content: str, *actions: FolderAction) -> None:
    kodi.plugin.expect(kodi.plugin._.setPluginCategory, 1337, title).returns(None)
    kodi.plugin.expect(kodi.plugin._.setContent, 1337, content).returns(None)
    for url, item, is_folder in actions:
        kodi.plugin.expect(kodi.plugin._.addDirectoryItem, 1337, url, item, is_folder).returns(value=True)
    kodi.plugin.expect(kodi.plugin._.endOfDirectory, 1337, cacheToDisc=False).returns(None)


def folder(kodi: Kodi, label: str, action: str) -> FolderAction:
    url = f"plugin://plugin.video.dropout?action={action}"
    item = kodi.ListItem.expected(
        label=label,
        path=url,
        art=AddonArt,
        prop_IsPlayable="false",
        call_addContextMenuItems=[
            {
                "items": [("_Settings", "RunPlugin(plugin://plugin.video.dropout?action=settings)")],
                "replaceItems": True,
            }
        ],
    )
    return (url, item, True)


def home_no_profile(kodi: Kodi) -> None:
    make_view(
        kodi,
        "_Dropout.tv Home",
        "episodes",
        folder(kodi, "_Select profile", "select_profile"),
        folder(kodi, "_Log off", "logout"),
    )


def home_logged_in(kodi: Kodi) -> None:
    make_view(
        kodi,
        "_Dropout.tv Home",
        "episodes",
        folder(kodi, "_Featured", "featured"),
        folder(kodi, "_Continue watching", "continue_watching"),
        folder(kodi, "_My list", "my_list"),
        folder(kodi, "_New Releases", "new_releases"),
        folder(kodi, "_Trending", "trending"),
        folder(kodi, "_Series", "series"),
        folder(kodi, "_Browse", "browse"),
        folder(kodi, "_Search", "search"),
        folder(kodi, "_Select profile", "select_profile"),
        folder(kodi, "_Log off", "logout"),
    )


def first_load(  # noqa: PLR0913, PLR0917
    plugin: Plugin,
    kodi: Kodi,
    dropout: Dropout,
    test_settings: Settings,
    profiles: Profiles,
    profile_selector: int | None,
) -> Dropout.Credentials:
    dprofiles, kprofiles = profiles
    add_settings(kodi, test_settings)
    credentials = dropout.signs_in(test_settings, profiles=dprofiles)
    if profile_selector is not None:
        kodi.logs_error("login stopped at profile-select")
        home_no_profile(kodi)
        kodi.selects_dialog(
            "_Select profile",
            kprofiles,
            profile_selector,
            preselect=-1,
            use_details=True,
        )
        kodi.is_playing(answer=False)
        dropout.selects_profile(dprofiles[profile_selector].index)
        kodi.refreshes()
    else:
        dropout.selects_profile(dprofiles[0].index)
        home_logged_in(kodi)
    plugin.visit()
    return credentials


def cached_load(
    *, plugin: Plugin, time_machine: TimeMachineFixture, test_settings: Settings
) -> Generator[None, str, None]:
    time_machine.shift(dt.timedelta(minutes=3))
    add_settings(plugin.kodi, test_settings)
    url = yield None
    plugin.visit(url)
    yield None


def uncached_load(  # noqa: PLR0913
    *,
    plugin: Plugin,
    time_machine: TimeMachineFixture,
    test_settings: Settings,
    dropout: Dropout,
    test_profiles: Profiles,
    previous: Dropout.Credentials,
    profile: int,
) -> Generator[Dropout.Credentials, str, None]:
    time_machine.shift(dt.timedelta(minutes=6))
    add_settings(plugin.kodi, test_settings)
    renewed = previous.renewed(token="renewed-token", session="renewed")
    dropout.session_resumes(renewed)
    dropout.profiles(renewed, test_profiles[0])
    dropout.selects_profile(profile)
    url = yield renewed
    plugin.visit(url)
    yield renewed


def sign_in(plugin: Plugin, test_settings: Settings, profiles: Profiles, profile: int | None) -> Dropout.Credentials:
    return first_load(plugin, plugin.kodi, plugin.dropout, test_settings, profiles, profile)


@pytest.fixture
def signed_in(plugin: Plugin, test_settings: Settings, test_profiles: Profiles) -> Dropout.Credentials:
    return sign_in(plugin, test_settings, test_profiles, 0)
