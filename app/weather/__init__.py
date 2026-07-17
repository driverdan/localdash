"""Weather feature: NWS-proxied current conditions + today's forecast.

Backs the homepage weather strip. A sibling feature beside timeseries, news,
and events — weather does not flow through collectors/ingest and stores
nothing: the shaped NWS payload lives in an in-process TTL cache only.

Pipeline: NWS (api.weather.gov, at the shared center from config) ->
service.py (discover + fetch + cache) -> /api/v1/weather/ (app/api/weather.py)
-> the home page strip.
"""
