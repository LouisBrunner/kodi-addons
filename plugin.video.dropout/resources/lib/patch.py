"""See https://kodi.wiki/view/Python_Problems#datetime.strptime."""

# FIXME(3.9): should be typing.Self
from typing_extensions import Self, override  # noqa: UP035


def monkey_patch() -> None:
    import datetime  # noqa: PLC0415
    import time  # noqa: PLC0415

    class _ProxyDT(datetime.datetime):
        _patched = True

        @override
        @classmethod
        def strptime(cls, date_string: str, date_format: str, /) -> Self:
            return cls(*(time.strptime(date_string, date_format)[:6]))

    if not getattr(datetime.datetime, "_patched", False):
        datetime.datetime = _ProxyDT  # ty:ignore[invalid-assignment]
