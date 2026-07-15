## Context

The news registry (`app/news/registry.py`, `SOURCES`) is the code source of truth for news
outlets; `sync_registry()` upserts it at startup. Adding an outlet is a data-only edit to that
list — no schema or code-path changes. Chattanooga News Chronicle is a WordPress site
(chattnewschronicle.com) that exposes both a primary feed (`/feed/`) and per-category feeds
(`/category/<slug>/feed/`).

## Goals / Non-Goals

**Goals:**
- Surface Chattanooga News Chronicle's local coverage on the news homepage.
- Fit the existing registry pattern with no new code or migration.

**Non-Goals:**
- Per-section categorization of this outlet's articles.
- Any change to fetching, clustering, storage, or API behavior.

## Decisions

**Use the primary site feed only, mapped to `news`.**
The primary feed (`https://www.chattnewschronicle.com/feed/`) is the actively-updated one
(refreshes hourly, current items). Its per-item `<category>` tags are not read by the app —
category is assigned per feed — so a single feed means all articles land under `news`, which is
the correct bucket for a general local outlet.

- *Alternative considered: register per-category feeds* (`/category/local|sports|business|...`).
  Rejected: only the `local` category is actively published; the topical category feeds are
  dormant (newest items ranging from Jan 2024 to Sep 2025) and would be filtered out by the
  homepage's 7-day window anyway, so they add polling and never-shown rows for no benefit.

**Reuse the registry's existing browser User-Agent.**
No per-source UA handling is needed; WordPress feeds do not rate-limit like the TownNews-hosted
sources.

## Risks / Trade-offs

- [Feed mixes national/syndicated items with local coverage] → Accepted; this is the same known
  caveat that already applies to Local 3 and Times Free Press, and is out of scope to filter here.
- [Outlet later activates topical sections] → Not addressed now; a future change can add those
  section feeds if they become active. The 7-day window makes speculative registration pointless
  today.
