import pytest
from time_machine import TimeMachineFixture

from tests.dropout import Dropout

from .common import Settings
from .conftest import Profiles, cached_load, make_view, sign_in, uncached_load
from .plugin import Plugin


@pytest.mark.usefixtures("signed_in")
def test_saved_credentials_work(
    plugin: Plugin,
    test_settings: Settings,
    time_machine: TimeMachineFixture,
) -> None:
    sesh = cached_load(
        plugin=plugin,
        time_machine=time_machine,
        test_settings=test_settings,
    )
    next(sesh)
    plugin.kodi.opens_settings()
    sesh.send("settings")


def test_saved_credentials_are_reused(
    plugin: Plugin,
    test_settings: Settings,
    test_profiles: Profiles,
    time_machine: TimeMachineFixture,
    signed_in: Dropout.Credentials,
) -> None:
    sesh = uncached_load(
        plugin=plugin,
        time_machine=time_machine,
        test_settings=test_settings,
        dropout=plugin.dropout,
        test_profiles=test_profiles,
        previous=signed_in,
        profile=0,
    )
    _renewed = next(sesh)
    plugin.kodi.opens_settings()
    sesh.send("settings")


def test_single_profile_auto_selected(plugin: Plugin, test_settings: Settings, test_profiles: Profiles) -> None:
    sign_in(plugin, test_settings, (test_profiles[0][:1], test_profiles[1][:1]), profile=None)


def test_switching_profile_uses_its_token(
    plugin: Plugin,
    test_settings: Settings,
    test_profiles: Profiles,
    time_machine: TimeMachineFixture,
    signed_in: Dropout.Credentials,
) -> None:
    kodi, dropout = plugin.kodi, plugin.dropout
    dprofiles, kprofiles = test_profiles

    switch = cached_load(plugin=plugin, time_machine=time_machine, test_settings=test_settings)
    next(switch)
    kodi.is_playing(answer=False)
    kodi.selects_dialog("_Select profile", kprofiles, 2, preselect=0, use_details=True)
    dropout.selects_profile(dprofiles[2].index)
    kodi.refreshes()
    switch.send("select_profile")

    listing = cached_load(plugin=plugin, time_machine=time_machine, test_settings=test_settings)
    next(listing)
    dropout.my_list(signed_in.for_profile(dprofiles[2].index), page=1, items=[], works=True)
    make_view(kodi, "__My list - Page 1", "videos")
    listing.send("my_list")


def test_saved_profile_uses_its_token(
    plugin: Plugin,
    test_settings: Settings,
    test_profiles: Profiles,
    time_machine: TimeMachineFixture,
    signed_in: Dropout.Credentials,
) -> None:
    session = uncached_load(
        plugin=plugin,
        time_machine=time_machine,
        test_settings=test_settings,
        dropout=plugin.dropout,
        test_profiles=test_profiles,
        previous=signed_in,
        profile=0,
    )
    renewed = next(session)
    plugin.dropout.my_list(renewed.for_profile(0), page=1, items=[], works=True)
    make_view(plugin.kodi, "__My list - Page 1", "videos")
    session.send("my_list")


def test_saved_cookies_without_a_scope_are_forgotten(
    plugin: Plugin, test_settings: Settings, test_profiles: Profiles
) -> None:
    plugin.has_legacy_cookies(_session="stale", logged_in="true")
    sign_in(plugin, test_settings, test_profiles, 0)
