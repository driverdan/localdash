"""Pins each upstream fetch's request settings: User-Agent, timeout, redirects, headers.

The expected values below are copied from the per-call-site table in
openspec/changes/add-shared-http-client/design.md (which records the request settings
before the move to app.http.make_client) and the `outbound-http` spec. A failure here
is a wire change: make it deliberately, by updating the spec, not just this table.

Each case drives the real fetch through the mock_http fixture. The handler answers the
first request with a 302 to a marker path; only sites that follow redirects then
request that path. Responses after that are minimal, so most fetches end in an error,
which is swallowed here: only what went out on the wire is asserted.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx
import pytest

from app.collectors import build_collectors
from app.collectors.epb import EpbCollector
from app.collectors.hc911 import HC911Collector
from app.collectors.tdot import TdotCollector
from app.collectors.tnaw import TnawCollector
from app.config import Settings, get_settings
from app.events.geocoding import NominatimGeocoder
from app.events.sources import build_sources
from app.events.sources.carcruisefinder import CarCruiseFinderSource
from app.events.sources.chattzoo import ChattZooSource
from app.events.sources.cityspark import CitySparkSource
from app.events.sources.ical import ICalSource
from app.events.sources.meetup import MeetupSource
from app.events.sources.tribe import TribeEventsSource
from app.http import BROWSER_USER_AGENT
from app.news import fetcher
from app.weather.service import WeatherService

APP_UA = "LocalDash-wire-test/1.0"
GEOCODER_UA = "LocalDash-wire-test/1.0 (geocoder)"
# The mainstream browser UA, spelled out so a change to the constant fails here too.
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
HTTPX_DEFAULT = object()  # sentinel: expect httpx's own python-httpx/<version>

REDIRECT_PATH = "/__wire_redirect__"

SETTINGS = Settings(
    _env_file=None,
    user_agent=APP_UA,
    events_geocoder_user_agent=GEOCODER_UA,
    events_meetup_token="wire-token",
    events_ical_feeds="https://ical.example/feed.ics",
    hc911_auth_token="wire-hc911-token",
    hc911_origin="https://origin.example",
    tdot_api_key="wire-tdot-key",
)


def _collector(cls):
    (c,) = [c for c in build_collectors(SETTINGS) if isinstance(c, cls)]
    return c


def _source(cls):
    (s,) = [s for s in build_sources(SETTINGS) if isinstance(s, cls)]
    return s


async def _geocode() -> None:
    # As events.refresh() builds it: UA from settings, everything else default.
    async with NominatimGeocoder(user_agent=SETTINGS.events_geocoder_user_agent) as geocoder:
        await geocoder.geocode("1800 Rossville Ave")


async def _weather() -> None:
    await WeatherService().get_current(force=True)


@dataclass
class Site:
    id: str
    run: Callable[[], Awaitable[object]]
    user_agent: object  # str, or HTTPX_DEFAULT
    timeout: float
    follows_redirects: bool
    headers: dict[str, str] = field(default_factory=dict)


SITES = [
    Site(
        "hc911",
        lambda: _collector(HC911Collector).fetch(),
        APP_UA,
        30,
        False,
        {
            "Content-Type": "application/json",
            "X-Frontend-Auth": "wire-hc911-token",
            "Origin": "https://origin.example",
        },
    ),
    Site(
        "tdot",
        lambda: _collector(TdotCollector).fetch(),
        APP_UA,
        30,
        False,
        {"X-API-Key": "wire-tdot-key"},
    ),
    Site(
        "epb",
        lambda: _collector(EpbCollector).fetch(),
        APP_UA,
        30,
        False,
        {"Accept": "application/json"},
    ),
    Site(
        "tnaw",
        lambda: _collector(TnawCollector).fetch(),
        APP_UA,
        30,
        False,
        {"Accept": "application/json"},
    ),
    Site("nominatim", _geocode, GEOCODER_UA, 10, False),
    Site("chattzoo", lambda: _source(ChattZooSource).fetch(), APP_UA, 20, True),
    Site(
        "meetup",
        lambda: _source(MeetupSource).fetch(),
        HTTPX_DEFAULT,
        20,
        False,
        {"Authorization": "Bearer wire-token", "Content-Type": "application/json"},
    ),
    Site("ical", lambda: _source(ICalSource).fetch(), HTTPX_DEFAULT, 20, True),
    Site("tribe", lambda: _source(TribeEventsSource).fetch(), HTTPX_DEFAULT, 30, True),
    Site("cityspark", lambda: _source(CitySparkSource).fetch(), HTTPX_DEFAULT, 30, False),
    Site("carcruisefinder", lambda: _source(CarCruiseFinderSource).fetch(), BROWSER_UA, 20, True),
    Site(
        "news_html",
        lambda: fetcher._fetch_html("https://news.example/listing"),
        BROWSER_UA,
        30,
        True,
    ),
    Site("weather", _weather, APP_UA, 10, True, {"Accept": "application/geo+json"}),
]


@pytest.fixture
def weather_settings(monkeypatch):
    """WeatherService reads get_settings(); point it at the test UA, with AirNow on."""
    monkeypatch.setenv("USER_AGENT", APP_UA)
    monkeypatch.setenv("AIRNOW_API_KEY", "wire-airnow-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _redirect_first(request: httpx.Request, sent: list[httpx.Request]) -> httpx.Response:
    sent.append(request)
    if len(sent) == 1:
        location = str(request.url.copy_with(path=REDIRECT_PATH, query=None))
        return httpx.Response(302, headers={"Location": location})
    return httpx.Response(200, json={})


@pytest.mark.parametrize("site", SITES, ids=[s.id for s in SITES])
async def test_request_settings(site: Site, mock_http, weather_settings):
    sent: list[httpx.Request] = []
    mock_http.install(lambda request: _redirect_first(request, sent))

    try:
        await site.run()
    except Exception:  # noqa: BLE001 — only the requests sent matter here
        pass

    assert sent, "the fetch sent no request"
    for request in sent:
        ua = request.headers.get("User-Agent")
        if site.user_agent is HTTPX_DEFAULT:
            assert ua == f"python-httpx/{httpx.__version__}"
            assert ua not in (APP_UA, BROWSER_UA)
        else:
            assert ua == site.user_agent
        t = site.timeout
        assert request.extensions["timeout"] == {"connect": t, "read": t, "write": t, "pool": t}
        for name, value in site.headers.items():
            assert request.headers.get(name) == value, name

    followed = [r for r in sent if r.url.path == REDIRECT_PATH]
    if site.follows_redirects:
        assert len(followed) == 1 and sent[1] is followed[0]
    else:
        assert followed == []


def test_browser_constant_matches_the_pinned_string():
    assert BROWSER_USER_AGENT == BROWSER_UA


def test_news_feed_parse_sends_the_browser_ua(monkeypatch):
    calls: list[tuple[tuple, dict]] = []

    def fake_parse(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(fetcher.feedparser, "parse", fake_parse)

    fetcher._parse_feed("https://feeds.example/rss")

    ((args, kwargs),) = calls
    assert args == ("https://feeds.example/rss",)
    assert kwargs["agent"] == BROWSER_UA
    assert kwargs["request_headers"] == {"Accept": "application/rss+xml, application/xml, */*"}
