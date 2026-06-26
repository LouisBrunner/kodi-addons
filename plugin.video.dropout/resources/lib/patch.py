"""See https://kodi.wiki/view/Python_Problems#datetime.strptime."""


def monkey_patch() -> None:
    import datetime  # noqa: PLC0415
    import time  # noqa: PLC0415

    class _ProxyDT(datetime.datetime):
        @classmethod
        def strptime(cls, date_string: str, fmt: str) -> datetime.datetime:
            return datetime.datetime(*(time.strptime(date_string, fmt)[:6]))  # noqa: DTZ001

    datetime.datetime = _ProxyDT  # ty:ignore[invalid-assignment]
