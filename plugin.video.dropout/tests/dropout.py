import json
import logging
import random
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import responses
from requests import PreparedRequest
from responses import matchers

from .common import Settings

logger = logging.getLogger(__name__)


class Dropout:
    @dataclass
    class Credentials:
        token: str
        user_id: int
        subscribed: bool
        session: str

        def renewed(self, token: str, session: str) -> "Dropout.Credentials":
            return Dropout.Credentials(token=token, user_id=self.user_id, subscribed=self.subscribed, session=session)

        def for_profile(self, index: int | str) -> "Dropout.Credentials":
            return Dropout.Credentials(
                token=f"{self.token}.profile{index}",
                user_id=self.user_id,
                subscribed=self.subscribed,
                session=self.session,
            )

    @dataclass
    class Profile:
        index: int
        name: str
        pin_locked: bool
        image: str

    _WEBSITE = "https://watch.dropout.tv"
    _API = "https://api.vhx.com/v2/sites/36348"
    _TV = "https://api.vhx.tv"

    def __init__(self, requests_mock: responses.RequestsMock) -> None:
        self.http = requests_mock
        self._counters = {}
        self._account: Dropout.Credentials | None = None
        self._session: str | None = None

    @classmethod
    def _cookies(cls, request: PreparedRequest) -> dict[str, str]:
        header = request.headers.get("Cookie", "")
        return dict(part.split("=", 1) for part in header.split("; ") if part)

    @classmethod
    def _no_session(cls, request: PreparedRequest) -> tuple[bool, str]:
        return "_session" not in cls._cookies(request), "the session cookie must not leave the website"

    @classmethod
    def _has_session(cls, session: str) -> Callable[[PreparedRequest], tuple[bool, str]]:
        def _match(request: PreparedRequest) -> tuple[bool, str]:
            sent = cls._cookies(request).get("_session")
            return sent == session, f"expected session {session!r}, got {sent!r}"

        return _match

    @classmethod
    def _log_request(cls, request: PreparedRequest) -> tuple[bool, str]:
        logger.info("[%-7s] %s %s (%s): %s", "request", request.method, request.url, request.headers, request.body)
        return (True, "")

    def _csrf_page(self, url: str) -> str:
        csrf = self._secret("csrf")
        page = f"""
<html><head>
<meta name="csrf-token" content="{csrf}">
</head><body>
<form id="login-form-password"><input type="hidden" name="authenticity_token" value="{csrf}"></form>
</body></html>
"""

        def _serve(request: PreparedRequest) -> tuple[int, dict[str, str], str]:
            if url == "/login" and "_session=" in request.headers.get("Cookie", ""):
                return (200, {}, "<html><body>You are already signed in.</body></html>")
            return (200, {}, page)

        self.http.add_callback(
            responses.GET,
            f"{self._WEBSITE}{url}",
            callback=_serve,
            content_type="text/html",
            match=[self._log_request, matchers.header_matcher({"Accept": re.compile(r"text/html")})],
        )
        return csrf

    @classmethod
    def _accepts_html(cls, request: PreparedRequest) -> tuple[bool, str]:
        accept = request.headers.get("Accept", "")
        return "text/html" in accept, f"Accept must allow text/html, got {accept!r}"

    def _home_logged_in(self, creds: Credentials) -> str:
        return f"""
<html><head>
<title>Dropout</title>
</head><body>
<p>Welcome to Dropout!</p>
<script>
window.VHX = window.VHX || {{}};
window.VHX.config = {{
  api_url: "https://api.vhx.tv",
  token: "{creds.token}",
  user_has_subscription: "{str(creds.subscribed).lower()}",
  profile_index: 0
}};
window._current_user = {{"id": {creds.user_id}, "user_id": {creds.user_id}}};</script>
</body></html>
"""

    def _home_logged_out(self) -> None:
        self.http.get(
            f"{self._WEBSITE}/",
            body="""
<html><head><title>Dropout</title></head><body>
<script>
window.VHX = window.VHX || {};
window.VHX.config = {
  api_url: "https://api.vhx.tv",
  token: "public-token",
  user_has_subscription: "false"
};</script>
</body></html>
""",
            match=[self._log_request, matchers.header_matcher({"Accept": re.compile(r"text/html")})],
        )

    def session_resumes(self, creds: Credentials) -> None:
        assert self._session is not None
        self._account = creds
        self.http.get(
            f"{self._WEBSITE}/",
            body=self._home_logged_in(creds),
            match=[
                self._log_request,
                matchers.header_matcher({"Accept": re.compile(r"text/html")}),
                self._has_session(self._session),
            ],
        )

    def login_works(self, settings: Settings, creds: Credentials) -> None:
        self._account = creds
        self._session = creds.session
        self._home_logged_out()
        csrf = self._csrf_page("/login")
        self.http.post(
            f"{self._WEBSITE}/login",
            body=self._home_logged_in(creds),
            headers={"Set-Cookie": f"_session={creds.session}; Domain=.dropout.tv; Path=/"},
            match=[
                self._log_request,
                matchers.urlencoded_params_matcher(
                    {
                        "email": settings.email,
                        "password": settings.password,
                        "authenticity_token": csrf,
                        "utf8": "True",
                    }
                ),
            ],
        )

    def login_fails(self, email: str, password: str) -> None:
        self._home_logged_out()
        csrf = self._csrf_page("/login")
        self.http.post(
            f"{self._WEBSITE}/login",
            status=422,
            body="invalid credentials",
            match=[
                self._log_request,
                matchers.urlencoded_params_matcher(
                    {
                        "email": email,
                        "password": password,
                        "authenticity_token": csrf,
                        "utf8": "True",
                    }
                ),
            ],
        )

    def profiles(self, creds: Credentials, profiles: list[Profile]) -> None:
        self.http.get(
            f"{self._API}/users/{creds.user_id}/profiles",
            json={
                "max_user_created_profiles": self._rand(len(profiles) * 2),
                "profiles": [
                    {
                        "index": profile.index,
                        "name": profile.name,
                        "pin_locked": profile.pin_locked,
                        "profile_image_url": profile.image,
                    }
                    for profile in profiles
                ],
            },
            match=[self._log_request, self._authorized(creds.token)],
        )

    def _secret(self, kind: str) -> str:
        cnt = self._counters.setdefault(kind, 0)
        self._counters[kind] = cnt + 1
        return f"{kind}{cnt}-{uuid.uuid4().hex[16:20]}"

    @classmethod
    def _rand(cls, rng: int) -> int:
        return int(random.random() * rng)  # noqa: S311

    def signs_in(self, settings: Settings, *, profiles: list[Profile], subscribed: bool = True) -> Credentials:
        creds = self.Credentials(
            token=self._secret("tkn"),
            user_id=self._rand(1_000_000),
            subscribed=subscribed,
            session=self._secret("sesh"),
        )
        self.login_works(settings, creds)
        if subscribed:
            self.profiles(creds, profiles)
        return creds

    def selects_profile(
        self,
        index: int,
        *,
        pin: str | None = None,
        accepted: bool = True,
    ) -> None:
        csrf = self._csrf_page("/")
        assert self._account is not None
        assert self._session is not None
        scoped = self._account.for_profile(index).token

        self.http.post(
            f"{self._WEBSITE}/profile/login",
            headers={"X-CSRF-Token": csrf},
            json={"access_token": scoped, "token_type": "Bearer", "expires_in": 7200} if accepted else None,
            match=[
                self._log_request,
                matchers.header_matcher({"X-CSRF-Token": csrf}),
                self._has_session(self._session),
                matchers.body_matcher(
                    json.dumps({"profile_index": index, **({"pin": pin} if pin is not None else {})})
                ),
            ],
            status=200 if accepted else 401,
        )

    def _authorized(self, token: str) -> Callable[[PreparedRequest], tuple[bool, str]]:
        bearer = matchers.header_matcher({"Authorization": f"Bearer {token}"})

        def _match(request: PreparedRequest) -> tuple[bool, str]:
            matched, reason = bearer(request)
            return (matched, reason) if not matched else self._no_session(request)

        return _match

    def browse(self, creds: Credentials, page: int, items: list, *, more: bool, works: bool) -> None:
        self.http.get(
            f"{self._TV}/browse",
            status=200 if works else 400,
            json={
                "_embedded": {"items": items},
                "_links": {"next": {"href": f"{self._TV}/browse?page={page + 1}"}} if more else {},
            }
            if works
            else None,
            match=[
                self._log_request,
                self._authorized(creds.token),
                matchers.query_param_matcher({"page": str(page)}),
            ],
        )

    def my_list(self, creds: Credentials, page: int, items: list, *, works: bool) -> None:
        self.http.get(
            f"{self._TV}/customers/{creds.user_id}/watchlist",
            status=200 if works else 400,
            json={"_embedded": {"items": items}, "_links": {}} if works else None,
            match=[
                self._log_request,
                self._authorized(creds.token),
                matchers.query_param_matcher({"page": str(page)}, strict_match=False),
            ],
        )

    def changes_list(self, creds: Credentials, id: int, *, add: bool, works: bool) -> None:
        self.http.add(
            responses.PUT if add else responses.DELETE,
            f"{self._TV}/me/watchlist",
            status=204 if works else 400,
            match=[
                self._log_request,
                self._authorized(creds.token),
                matchers.query_param_matcher({"collection": f"{self._TV}/collections/{id}"}),
            ],
        )

    def searches(self, creds: Credentials, query: str, page: int, results: list, *, more: bool, works: bool) -> None:  # noqa: PLR0913
        self.http.get(
            f"{self._API}/search",
            status=200 if works else 400,
            json={
                "pagination": {
                    "count": len(results) * 2 if more else len(results) / 2,
                    "page": page,
                    "per_page": 25,
                    "template_url": "",
                },
                "results": results,
            }
            if works
            else None,
            match=[
                self._log_request,
                self._authorized(creds.token),
                matchers.query_param_matcher({"q": query, "page": str(page), "per_page": "25"}),
            ],
        )

    def logs_out(self, *, works: bool = True) -> None:
        csrf = self._csrf_page("/")
        self.http.post(
            f"{self._WEBSITE}/logout",
            status=200 if works else 400,
            match=[self._log_request, matchers.urlencoded_params_matcher({"authenticity_token": csrf})],
        )
