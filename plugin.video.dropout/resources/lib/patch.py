"""See https://kodi.wiki/view/Python_Problems#datetime.strptime."""

from typing import Self


def monkey_patch() -> None:
    import datetime  # noqa: PLC0415
    import time  # noqa: PLC0415

    class _ProxyDT(datetime.datetime):
        _patched = True

        @classmethod
        def strptime(cls, date_string: str, date_format: str, /) -> Self:
            return cls(*(time.strptime(date_string, date_format)[:6]))

    if not getattr(datetime.datetime, "_patched", False):
        datetime.datetime = _ProxyDT  # ty:ignore[invalid-assignment]
