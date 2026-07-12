"""News feature: RSS aggregation of local outlets with cross-outlet story clustering.

Sibling of the geo timeseries pipeline — articles never flow through
collectors/ingest. Pipeline: fetch (fetcher.py) -> cluster (clustering.py) ->
serve (stories.py, exposed by app/api/news.py under /api/v1/news/).
"""
