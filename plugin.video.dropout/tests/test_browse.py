from collections.abc import Generator

import pytest
from time_machine import TimeMachineFixture

from .common import Settings
from .conftest import cached_load, folder, make_view
from .dropout import Dropout
from .plugin import Plugin


def _art(src: str) -> dict[str, str]:
    return {
        "poster": f"{src}?w=1000&h=1500&fit=crop",
        "fanart": f"{src}?w=1920&h=1080&fit=crop",
        "banner": f"{src}?w=1000&h=185&fit=crop",
        "thumb": f"{src}?w=1280&h=720&fit=crop",
        "landscape": f"{src}?w=1280&h=720&fit=crop",
    }


JSON = dict[str, object]


@pytest.fixture
def browse_one_item(dropout: Dropout, signed_in: Dropout.Credentials) -> tuple[JSON, Generator[JSON]]:
    creds = signed_in.for_profile(0)

    item: JSON = {
        "type": "video",
        "id": 7,
        "title": "Dimension 20: Trailer",
        "url": "dimension-20-trailer",
        "short_description": "Dungeons & Dragons actual play series trailer",
        "description": "Lorem ipsum dolor sit amet...",
        "duration": {"seconds": 90},
        "thumbnail": {"source": "https://images.example.test/d20-trailer.jpg"},
        "created_at": "2026-01-15T12:00:00Z",
        "updated_at": "2026-01-16T12:00:00Z",
    }

    def _gen() -> Generator[JSON]:
        dropout.browse(creds, page=1, items=[item], more=False, works=True)
        yield item

    return item, _gen()


@pytest.fixture
def browse_100_items(dropout: Dropout, signed_in: Dropout.Credentials) -> Generator[list[JSON]]:
    creds = signed_in.for_profile(0)

    def _gen() -> Generator[list[JSON]]:
        for p in range(1, 10):
            items: list[JSON] = []
            for e in range(1, 5):
                i = p * 7 + e
                items.append(
                    {
                        "type": "video",
                        "id": 12 + i,
                        "title": f"Dimension 20: Fantasy High: Senior Year - Episode {i}",
                        "url": f"fantasy-high-senior-year-{i}",
                        "short_description": f"Follow up of Fantasy High: Junior Year (episode {i})",
                        "description": f"Episode {i}: Lorem ipsum dolor sit amet...",
                        "duration": {"seconds": 120 + (i % 15 + 1) * 300},
                        "thumbnail": {"source": f"https://images.example.test/d20-ep-{i}.jpg"},
                        "created_at": f"2026-{i // 12 + 1:02}-{i % 20 + 1:02}T12:00:00Z",
                        "updated_at": f"2026-{i // 12 + 1:02}-{i % 20 + 1:02}T12:00:00Z",
                    }
                )
            dropout.browse(creds, page=p, items=items, more=p != 10, works=True)
            yield items

    return _gen()


def test_browse_one_item(
    plugin: Plugin,
    test_settings: Settings,
    time_machine: TimeMachineFixture,
    signed_in: Dropout.Credentials,
    browse_one_item: tuple[JSON, Generator[JSON]],
) -> None:
    kodi, dropout = plugin.kodi, plugin.dropout
    creds = signed_in.for_profile(0)
    video = kodi.ListItem.expected(
        label="Dimension 20: Trailer",
        label2="Dungeons & Dragons actual play series trailer",
        path="plugin://plugin.video.dropout?slug=dimension-20-trailer&action=play",
        art=_art("https://images.example.test/d20-trailer.jpg"),
        prop_video={},
        prop_IsPlayable="true",
        **{"prop_plugin.video.dropout.video_id": "7"},
        videoInfoTag=kodi.InfoTagVideo.expected(
            title="Dimension 20: Trailer",
            plotOutline="Dungeons & Dragons actual play series trailer",
            tagLine="Dungeons & Dragons actual play series trailer",
            plot="Lorem ipsum dolor sit amet...",
            dateAdded="January 15, 2026",
            duration=90,
            mediaType="video",
        ),
        call_addContextMenuItems=[
            {
                "items": [
                    (
                        "_Add to my list",
                        "RunPlugin(plugin://plugin.video.dropout?entity_type=video&entity_id=7&action=add_to_list)",
                    ),
                    ("_Settings", "RunPlugin(plugin://plugin.video.dropout?action=settings)"),
                ],
                "replaceItems": True,
            }
        ],
    )

    _, browse_one_item_ = browse_one_item
    listing = cached_load(plugin=plugin, time_machine=time_machine, test_settings=test_settings)
    next(listing)
    dropout.my_list(creds, page=None, items=[], works=True)
    next(browse_one_item_)
    make_view(kodi, "__Browse - Page 1", "videos", (video.path, video, {"isFolder": False, "totalItems": 1}))
    listing.send("browse")


def test_browse_in_list(
    plugin: Plugin,
    test_settings: Settings,
    time_machine: TimeMachineFixture,
    signed_in: Dropout.Credentials,
    browse_one_item: tuple[JSON, Generator[JSON]],
) -> None:
    kodi, dropout = plugin.kodi, plugin.dropout
    creds = signed_in.for_profile(0)
    video = kodi.ListItem.expected(
        label="Dimension 20: Trailer",
        label2="Dungeons & Dragons actual play series trailer",
        path="plugin://plugin.video.dropout?slug=dimension-20-trailer&action=play",
        art=_art("https://images.example.test/d20-trailer.jpg"),
        prop_video={},
        prop_IsPlayable="true",
        **{"prop_plugin.video.dropout.video_id": "7"},
        videoInfoTag=kodi.InfoTagVideo.expected(
            title="Dimension 20: Trailer",
            plotOutline="Dungeons & Dragons actual play series trailer",
            tagLine="Dungeons & Dragons actual play series trailer",
            plot="Lorem ipsum dolor sit amet...",
            dateAdded="January 15, 2026",
            duration=90,
            mediaType="video",
        ),
        call_addContextMenuItems=[
            {
                "items": [
                    (
                        "_Remove from my list",
                        "RunPlugin(plugin://plugin.video.dropout?entity_type=video&entity_id=7&action=remove_from_list)",
                    ),
                    ("_Settings", "RunPlugin(plugin://plugin.video.dropout?action=settings)"),
                ],
                "replaceItems": True,
            }
        ],
    )

    item, browse_one_item_ = browse_one_item
    listing = cached_load(plugin=plugin, time_machine=time_machine, test_settings=test_settings)
    next(listing)
    dropout.my_list(creds, page=None, items=[item], works=True)
    next(browse_one_item_)
    make_view(kodi, "__Browse - Page 1", "videos", (video.path, video, {"isFolder": False, "totalItems": 1}))
    listing.send("browse")


def test_browse_multiple_items(
    plugin: Plugin,
    test_settings: Settings,
    time_machine: TimeMachineFixture,
    signed_in: Dropout.Credentials,
    browse_100_items: Generator[list[JSON]],
) -> None:
    kodi, dropout = plugin.kodi, plugin.dropout
    creds = signed_in.for_profile(0)
    videos = []
    for i in range(1, 5):
        video = kodi.ListItem.expected(
            label=f"Dimension 20: Fantasy High: Senior Year - Episode {i + 7}",
            label2=f"Follow up of Fantasy High: Junior Year (episode {i + 7})",
            path=f"plugin://plugin.video.dropout?slug=fantasy-high-senior-year-{i + 7}&action=play",
            art=_art(f"https://images.example.test/d20-ep-{i + 7}.jpg"),
            prop_video={},
            prop_IsPlayable="true",
            **{"prop_plugin.video.dropout.video_id": f"{19 + i}"},
            videoInfoTag=kodi.InfoTagVideo.expected(
                title=f"Dimension 20: Fantasy High: Senior Year - Episode {i + 7}",
                plotOutline=f"Follow up of Fantasy High: Junior Year (episode {i + 7})",
                tagLine=f"Follow up of Fantasy High: Junior Year (episode {i + 7})",
                plot=f"Episode {i + 7}: Lorem ipsum dolor sit amet...",
                dateAdded=f"January {i + 8:02}, 2026",
                duration=2520 + 300 * i,
                mediaType="video",
            ),
            call_addContextMenuItems=[
                {
                    "items": [
                        (
                            "_Add to my list",
                            (
                                "RunPlugin(plugin://plugin.video.dropout"
                                f"?entity_type=video&entity_id={19 + i}&action=add_to_list)"
                            ),
                        ),
                        ("_Settings", "RunPlugin(plugin://plugin.video.dropout?action=settings)"),
                    ],
                    "replaceItems": True,
                }
            ],
        )
        videos.append((video.path, video, {"isFolder": False, "totalItems": 4}))
    videos.append(folder(kodi, "_Next - Page 2", "browse", args="page=2&", prop_SpecialSort="bottom"))

    listing = cached_load(plugin=plugin, time_machine=time_machine, test_settings=test_settings)
    next(listing)
    dropout.my_list(creds, page=None, items=[], works=True)
    next(browse_100_items)
    make_view(kodi, "__Browse - Page 1", "videos", *videos)
    listing.send("browse")
