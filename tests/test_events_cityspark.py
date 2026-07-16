"""Offline tests for the CitySpark source (fixture payload, no network).

The fixture is a trimmed real capture: five events plus the tag-vocabulary
slice they reference, merged with the bootstrap's baseUrl the same way
fetch() assembles the parse payload.
"""

import datetime as dt
import json
from pathlib import Path

import httpx

from app.events.sources.cityspark import (
    MAX_PAGES,
    PAGE_SIZE,
    CitySparkSource,
    parse_bootstrap,
    parse_payload,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cityspark" / "payload.json"
UTC = dt.timezone.utc


def load_payload() -> dict:
    return json.loads(FIXTURE.read_text())


def make_payload(events: list[dict], all_tags: list[dict] | None = None) -> dict:
    """A minimal synthetic parse payload for single-scenario tests."""
    return {"Value": events, "AllTags": all_tags or [], "baseUrl": "https://example.org/cal#/"}


# Vocabulary slice used by the synthetic rollup tests, mirroring the real
# ids: Performing Arts (root) > Music > {Live Music, MusicEvent}; Nightlife
# is a bare root.
VOCAB = [
    {"id": 2, "name": "Performing Arts", "parent": None},
    {"id": 17, "name": "Music", "parent": 2},
    {"id": 10262, "name": "Live Music", "parent": 17},
    {"id": 1, "name": "MusicEvent", "parent": 17},
    {"id": 14, "name": "Nightlife", "parent": None},
]


def make_event(**overrides) -> dict:
    base = {
        "Id": "test-id",
        "PId": 12345,
        "Name": "Test Event",
        "StartUTC": "2026-07-15T12:00:00Z",
        "latitude": 35.0,
        "longitude": -85.3,
        "Tags": [],
        "PrimaryUrl": "https://example.org/event",
    }
    base.update(overrides)
    return base


# --- parse: fixture ---


def test_parse_payload_extracts_all_fixture_events():
    events = parse_payload(load_payload())

    assert len(events) == 5
    assert all(e.source_name == "CitySpark" for e in events)
    assert all(e.start_time.tzinfo is not None for e in events)
    assert all(e.latitude is not None and e.longitude is not None for e in events)
    assert all(e.source_event_id for e in events)


def test_parse_payload_maps_fields():
    events = parse_payload(load_payload())
    (showcase,) = [e for e in events if e.title == "Teen Artist Showcase"]

    assert showcase.end_time == dt.datetime(2026, 7, 15, 23, 0, tzinfo=UTC)
    assert showcase.venue_name == "Chattanooga State"
    assert showcase.address == "4501 Amicola Hwy, Chattanooga, TN, 37406"
    assert (showcase.latitude, showcase.longitude) == (35.098289, -85.243929)
    assert showcase.source_url == "https://chattanoogastate.edu/humanities-fine-arts"
    assert showcase.source_event_id == "260702WIel1RbR8EKw3o80AWlhUg"


def test_start_utc_is_used_and_datestart_ignored():
    # The 4-hour trap, from the real capture: DateStart carries a "Z" on what
    # is actually 08:00 EDT; StartUTC is the true UTC instant.
    payload = load_payload()
    (raw,) = [e for e in payload["Value"] if e["Name"] == "Teen Artist Showcase"]
    assert raw["DateStart"] == "2026-07-15T08:00:00Z"
    assert raw["StartUTC"] == "2026-07-15T12:00:00Z"

    events = parse_payload(payload)
    (showcase,) = [e for e in events if e.title == "Teen Artist Showcase"]
    assert showcase.start_time == dt.datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def test_event_without_startutc_is_skipped_and_parse_continues():
    payload = make_payload(
        [
            make_event(Id="a", Name="No Start", StartUTC=None, DateStart="2026-07-15T08:00:00Z"),
            make_event(Id="b", Name="Has Start"),
        ]
    )
    events = parse_payload(payload)

    assert [e.title for e in events] == ["Has Start"]


def test_missing_endutc_yields_none():
    events = parse_payload(load_payload())
    (open_mic,) = [e for e in events if e.title == "Open Mic Night- Arts"]
    assert open_mic.end_time is None


def test_event_without_any_url_falls_back_to_the_widget_detail_page():
    events = parse_payload(load_payload())
    (comedy,) = [e for e in events if e.title == "Open mic comedy"]
    assert (
        comedy.source_url
        == "https://www.chattanoogapulse.com/local-events-calendar#/details/open-mic-comedy/18320007"
    )


# --- parse: depth-1 tag rollup ---


def test_tag_rolls_up_to_one_level_below_the_root():
    (event,) = parse_payload(make_payload([make_event(Tags=[10262])], VOCAB))
    assert event.tags == ["music"]  # neither "live music" nor "performing arts"


def test_root_tag_resolves_to_itself():
    (event,) = parse_payload(make_payload([make_event(Tags=[14])], VOCAB))
    assert event.tags == ["nightlife"]


def test_leaves_under_one_depth1_node_collapse_to_a_single_tag():
    (event,) = parse_payload(make_payload([make_event(Tags=[10262, 1])], VOCAB))
    assert event.tags == ["music"]


def test_unmappable_tag_id_is_skipped_and_event_survives():
    (event,) = parse_payload(make_payload([make_event(Tags=[99999, 10262])], VOCAB))
    assert event.tags == ["music"]


def test_cyclic_parent_chain_terminates_and_event_survives():
    cyclic = [
        {"id": 1, "name": "A", "parent": 2},
        {"id": 2, "name": "B", "parent": 1},
    ]
    (event,) = parse_payload(make_payload([make_event(Tags=[1])], cyclic))
    assert event.tags  # terminated with some name rather than hanging


def test_dangling_parent_resolves_to_the_deepest_reachable_node():
    dangling = [
        {"id": 1, "name": "Leaf", "parent": 2},
        {"id": 2, "name": "Reachable", "parent": 99999},
    ]
    (event,) = parse_payload(make_payload([make_event(Tags=[1])], dangling))
    assert event.tags == ["reachable"]


# --- fetch: bootstrap + pagination ---


def make_bootstrap(all_tags: list[dict] | None = None) -> str:
    locals_json = json.dumps({"AllTags": all_tags or VOCAB, "baseUrl": "https://example.org/cal#/"})
    return f"var cSparkLocals = {locals_json};\n(function(){{/* widget bundle */}})();"


def test_parse_bootstrap_extracts_the_locals_object():
    locals_dict = parse_bootstrap(make_bootstrap())
    assert locals_dict["baseUrl"] == "https://example.org/cal#/"
    assert len(locals_dict["AllTags"]) == len(VOCAB)


def make_source(**overrides) -> CitySparkSource:
    kwargs = dict(
        slug="TestPortal", ppid=9824, lat=35.0456, lon=-85.3097, radius_miles=25, lookahead_days=14
    )
    kwargs.update(overrides)
    return CitySparkSource(**kwargs)


def install_transport(monkeypatch, handler):
    """Route the source's httpx client through a mock transport."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def fake_client(**kwargs):
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr("app.events.sources.cityspark.httpx.AsyncClient", fake_client)


def paged_handler(pages: list[list[dict]], requests: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, text=make_bootstrap())
        skip = json.loads(request.content)["skip"]
        index = skip // PAGE_SIZE
        value = pages[index] if index < len(pages) else []
        return httpx.Response(200, json={"Value": value, "Success": True, "ErrorMessage": None})

    return handler


async def test_fetch_paginates_until_a_short_page_and_dedupes_by_id(monkeypatch):
    def page(start: int, count: int) -> list[dict]:
        return [make_event(Id=f"ev-{i}", Name=f"Event {i}") for i in range(start, start + count)]

    pages = [page(0, PAGE_SIZE), page(100, PAGE_SIZE), page(200, 26)]
    pages[1][0]["Id"] = "ev-0"  # repeated across pages: deduped
    requests: list[httpx.Request] = []
    install_transport(monkeypatch, paged_handler(pages, requests))

    events = await make_source().fetch()

    assert len(events) == 225  # 226 listings minus the cross-page duplicate
    posts = [r for r in requests if r.method == "POST"]
    assert len(posts) == 3  # stopped on the short page
    bodies = [json.loads(r.content) for r in posts]
    assert [b["skip"] for b in bodies] == [0, 100, 200]
    assert all(b["end"] for b in bodies)  # end always set: null caps the API at one day


async def test_fetch_empty_result_yields_zero_events(monkeypatch):
    requests: list[httpx.Request] = []
    install_transport(monkeypatch, paged_handler([], requests))

    events = await make_source().fetch()

    assert events == []
    assert len([r for r in requests if r.method == "POST"]) == 1


async def test_fetch_page_cap_bounds_a_non_terminating_loop(monkeypatch):
    full_page = [make_event(Id="same-id", Name="Repeat")] * PAGE_SIZE

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=make_bootstrap())
        return httpx.Response(200, json={"Value": full_page, "Success": True})

    install_transport(monkeypatch, handler)
    events = await make_source().fetch()

    assert len(events) == 1  # every page repeated one Id; the cap ended the loop


async def test_fetch_sends_no_auth_referer_or_spoofed_ua(monkeypatch):
    requests: list[httpx.Request] = []
    install_transport(monkeypatch, paged_handler([], requests))

    await make_source().fetch()

    for request in requests:
        assert "authorization" not in request.headers
        assert "referer" not in request.headers
        assert request.headers["user-agent"].startswith("python-httpx/")


# --- registry + failure isolation ---


def test_build_sources_registers_cityspark_by_default():
    from app.config import Settings
    from app.events.sources import build_sources

    sources = build_sources(Settings(_env_file=None))
    (cityspark,) = [s for s in sources if isinstance(s, CitySparkSource)]
    assert cityspark.slug == "ChattanoogaPulse"
    assert cityspark.ppid == 9824
    assert cityspark.radius_miles == 25
    assert cityspark.lookahead_days == 14


def test_build_sources_omits_cityspark_when_disabled():
    from app.config import Settings
    from app.events.sources import build_sources

    sources = build_sources(Settings(_env_file=None, events_cityspark_enabled=False))
    assert not [s for s in sources if isinstance(s, CitySparkSource)]


async def test_failing_cityspark_source_does_not_abort_the_refresh_cycle(
    monkeypatch, events_db_session
):
    from app.events.ingest import run_sources
    from tests.fakes import FakeSource
    from tests.test_events_ingest import make_raw

    install_transport(monkeypatch, lambda request: httpx.Response(500))

    stats = await run_sources(
        events_db_session, [make_source(), FakeSource([make_raw("test-fake")])]
    )

    assert stats["created"] == 1


# The page-cap guard must actually be finite.
def test_max_pages_is_a_small_bound():
    assert 0 < MAX_PAGES <= 100
