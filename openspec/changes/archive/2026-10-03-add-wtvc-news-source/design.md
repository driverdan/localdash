## Context

The news registry (`app/news/registry.py`, `SOURCES`) is the code source of truth for outlets, and
`sync_registry()` upserts it at startup. WTVC (NewsChannel 9, ABC) is a Sinclair station whose
newsroom also produces the news on its sister station FOX Chattanooga (WDSI, `foxchattanooga.com`,
copyright "WTVCFOX"). Neither site advertises a feed in its HTML, but both serve Sinclair's
section-RSS convention, `/<section-path>.rss` (verified 2026-10-03, browser UA, HTTP 200):

| Feed | Contents |
|---|---|
| `/news/local.rss` | 41 items covering about 3 days, all `/news/local/…` URLs |
| `/sports.rss` | High school, UTC and AP sports, mixed with `/news/offbeat` and `/news/local` items |
| `/news.rss` | Videos, "skyview" camera pages, offbeat and nation-world stories; items as old as 2018 |
| `/news/nation-world.rss`, `/news/offbeat.rss` | National wire and novelty stories |
| `/news/{politics,crime,business}.rss` | HTTP 400 (no such sections) |

The feeds are valid RSS 2.0 (feedparser reports `bozo: False`). Every item has an image
`<enclosure type="image/jpeg">`, a GUID equal to its article URL, and a single
`<category>article</category>`. Descriptions are cut by the CMS at about 160 characters,
mid-word. When the two sites' `local.rss` feeds were compared on 2026-10-03, 37 of 41 items were
identical; each site also had 4 items the other lacked.

## Goals / Non-Goals

**Goals:**
- Add WTVC's local reporting to the news page and to cross-outlet clustering.
- Fit the existing registry pattern with no new code path, schema change or migration.

**Non-Goals:**
- Adding `foxchattanooga.com` as an outlet, now or alongside WTVC.
- Filtering off-region items out of WTVC's "Local" feed.
- Repairing Sinclair's mid-word 160-character descriptions.
- Any change to fetching, storage, clustering or API behavior.

## Decisions

**One outlet, NewsChannel 9, rather than FOX Chattanooga or both.**
Both sites publish the same newsroom's stories under the same URL slugs. Registering both would
make every WTVC story cluster as two outlets with two near-identical links. That inflates
`source_count` and implies corroboration that isn't there. NewsChannel 9 is the newsroom's
flagship brand, and the items it had that FOX Chattanooga lacked were Chattanooga-area stories
(Riverfront fundraising, an I-24 crash, Marion County). FOX Chattanooga's extra items were mostly
regional or national (North Carolina SNAP, a Kentucky manhunt).
- *Alternative: FOX Chattanooga.* Rejected. It has the same content, but it's the secondary
  brand and its extra items were less local.
- *Alternative: both.* Rejected because of the double counting described above.

**A single feed, `/news/local.rss`, with category `news`.**
Content categorization (feed tag → keyword → feed-section fallback) already moves sports stories
out of a general feed. WTVC's local feed carries its high school football and TSSAA coverage,
which the sports keywords catch. Adding `/sports.rss` would bring in offbeat and local items that
match no keyword and would then fall back to `sports`. In a sample, "TWRA commission meeting at
Bristol Motor Speedway" would have been filed as sports. It would also add national AP sports.
- *Alternative: `/sports.rss` + `/news/local.rss`.* Rejected for the misfiling reason above.
  It can be revisited if sports coverage looks thin in practice.
- *Alternative: `/news.rss`.* Rejected. It's a stale mix of videos, camera pages and national
  stories.

**Register with `use_feed_tags: False`.**
`article` isn't in `TAG_CATEGORY_MAP`, so today the tag would be ignored anyway. The flag records
that Sinclair's tag is a content type rather than a topic. Without it, a future map entry or a
Sinclair tag change (for example, adding `News`) could silently misfile every WTVC item. The
library entry made the same choice.

**Canonical apex homepage and feed URL (`https://newschannel9.com`).**
The feed's own `<link>` and `atom:link` use the apex host, and the apex serves 200 with no
redirect. `www.` also serves the feed, but the apex is what the site declares.

**Slug `wtvc`, name "NewsChannel 9 (WTVC)".**
This mirrors "Local 3 News (WRCB)": the brand viewers know, with call letters to tell it apart.

## Risks / Trade-offs

- [The "Local" feed includes Sinclair sister-station and wire content: about 15–25% in a sample,
  for example North Carolina stories (likely from WLOS Asheville), AP national, Kentucky] →
  Accepted and documented in the registry comment, the same as the Times Free Press and Local 3
  caveats. These items rarely cluster with Chattanooga outlets, so they appear as single-outlet
  stories.
- [Descriptions are cut mid-word at about 160 characters with no ellipsis, and
  `truncate_sentences` leaves text under 400 characters alone] → Only visible when WTVC is a
  story's only outlet or has its wordiest summary. Out of scope here; a general "no closing
  punctuation → trim to the last word and add '…'" fix could follow if it bothers us.
- [Sinclair restructures section URLs or rate-limits feed readers] → Handled like any feed error:
  per-feed isolation records it on `last_status` in the feed-health footer.
- [`robots.txt` disallows named AI crawlers (including `anthropic-ai`/`ClaudeBot`) but allows
  `*`] → localdash is a personal feed reader polling a published RSS feed every 15 minutes with
  the registry's browser UA. It isn't a crawler, and the `*` rules allow `/`.

## Migration Plan

Deploy is a normal rebuild (`docker compose up --build`). `sync_registry()` inserts the source and
feed rows at startup, and the startup refresh fetches the feed right away. To roll back, remove the
entry. On the next startup, `sync_registry()` deletes the feed row so it stops being fetched;
already-stored articles age out of the 7-day story window.

## Open Questions

None.
