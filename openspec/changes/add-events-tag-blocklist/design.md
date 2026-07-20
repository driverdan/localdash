## Context

Event tags are created lazily during ingest (`app/events/ingest.py`): keyword-derived topics come
from `tag_event()` in `app/events/tagging.py`, source-supplied tags are lowercased, and both flow
through `_get_or_create_tag()` into a unique, case-sensitive lowercase `tags` table joined M:N to
events via `event_tags` (`ondelete="CASCADE"` on both foreign keys). There is no fixed vocabulary
and no way to suppress a topic — a removed tag reappears on the next ingest. Every other operational
knob in the events feature is a `pydantic-settings` config value in `app/config.py`; there is no
admin UI or mutation endpoint. This change follows that pattern.

## Goals / Non-Goals

**Goals:**
- A declarative, env-driven blocklist (`events_blocked_tags`) that keeps named topics out of the
  system permanently.
- Purge already-stored blocked tags (and their event associations) on startup.
- Prevent blocked tags from being (re-)created or attached during ingest, for both keyword-derived
  and source-supplied tags.

**Non-Goals:**
- No runtime/UI editing of the blocklist — it is config, edited and applied by restart.
- No new API-layer filtering. Once purged and prevented, blocked tags simply do not exist, so
  `/api/v1/events/tags` and `?topic=` need no changes.
- No schema/migration change; rely on the existing `event_tags` cascade.
- No blocking of substrings/patterns — exact (normalized) tag-name matching only.

## Decisions

**1. Config setting shape — comma-separated string, normalized to a set.**
`events_blocked_tags: str = ""`, parsed by splitting on commas, stripping whitespace, lowercasing,
and dropping empties. This mirrors `events_ical_feeds` (comma-separated) and the existing
lowercase-on-store tag rule, so blocklist entries compare equal to stored names. A helper (e.g. a
`blocked_tags` property or a small function) centralizes normalization so ingest and startup share
one definition. *Alternative considered:* a `list[str]` setting — rejected for consistency with the
existing comma-separated string conventions and env ergonomics.

**2. Startup purge in the lifespan handler.**
The `lifespan` in `app/main.py` already opens a `SessionLocal()` session (to `sync_registry`) before
the scheduler starts. Add a single `DELETE FROM tags WHERE name IN (:blocked)` there, guarded by a
non-empty blocklist. The `event_tags` cascade removes associations; migrations have already run by
this point (compose runs `alembic upgrade head` first). *Alternative considered:* purging inside the
refresh cycle — rejected because startup is the natural once-per-deploy hook and keeps the delete off
the hot refresh path.

**3. Ingest strips blocked names from the computed set.**
In the branch that computes `names` (keyword-derived or source-supplied), subtract the blocklist set
before the `_get_or_create_tag` loop: `names -= blocked`. One filter point covers both sources of
tags and guarantees no blocked tag is ever created. *Alternative considered:* filtering inside
`_get_or_create_tag` — rejected as too deep; the set-difference at the call site is clearer and keeps
the blocklist concern in one place.

## Risks / Trade-offs

- **[Stale tags between config change and restart]** Adding a name to the blocklist takes effect only
  at the next startup (purge) and ingest (prevention). → Acceptable: config changes already require a
  restart in this app; the startup purge makes "edit env + restart" fully sufficient.
- **[Blocklist and keyword map drift]** A blocked topic that is also a keyword topic still runs
  keyword matching, then gets filtered out — slightly wasteful but harmless and keeps `tagging.py`
  untouched. → Accept; avoids coupling the blocklist to the code-defined vocabulary.
- **[Case/whitespace mismatch]** If normalization diverged between startup and ingest, a tag could be
  purged but re-created (or vice-versa). → Mitigated by sharing a single normalization helper for
  both paths.
