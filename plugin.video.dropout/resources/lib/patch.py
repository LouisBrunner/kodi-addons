"""See https://kodi.wiki/view/Python_Problems#datetime.strptime."""


def monkey_patch():
    import datetime
    import time

    class proxydt(datetime.datetime):
        @classmethod
        def strptime(cls, date_string, format):
            return datetime.datetime(*(time.strptime(date_string, format)[:6]))

    datetime.datetime = proxydt
