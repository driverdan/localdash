## 1. Ingest writes the status

- [x] 1.1 In `app/ingest.py`, add a private helper (e.g. `_latest_properties(obs)`) returning `{**obs.properties, "status": obs.status}`, with a short docstring: ingest owns the entity's status key, and the normalized status overrides any raw `status`
- [x] 1.2 Use the helper for `latest_properties` in both the create path (`Entity(...)`) and the update path of `ingest()`
- [x] 1.3 Add a comment at the change-detection call (`state_changed(...)`) saying the previous status was written by ingest on the last poll, not by the collector
- [x] 1.4 Leave `_observation` and `_entity_feature` unchanged (observation status lives in its column; diffs already pass `status=obs.status`)

## 2. Collectors stop copying status

- [x] 2.1 `app/collectors/epb.py`: drop `"status": ...` from `properties` (keep `**item` and `service`) and remove the comment explaining the copy
- [x] 2.2 `app/collectors/tnaw.py`: drop `"status": status` from `properties` (keep `advisory_type`) and reword the EventType comment so it no longer says ingest and the frontend read `properties["status"]`

## 3. Tests

- [x] 3.1 `tests/test_ingest.py`: change the `_obs` and `_poly_obs` helpers to stop putting `status` in `properties`, so the existing lifecycle, diff-contract, and polygon tests exercise the new contract
- [x] 3.2 `tests/test_ingest.py`: new DB test where an unchanged second poll with no `status` in properties records no observation and produces an empty diff, and the entity's `latest_properties["status"]` equals the normalized status
- [x] 3.3 `tests/test_ingest.py`: new DB test where a raw `properties["status"]` differs from `obs.status`: the stored `latest_properties["status"]` is the normalized value, and a repeat poll with the same normalized status records nothing
- [x] 3.4 `tests/test_ingest.py`: new DB test where `obs.status` is `None`: `latest_properties` contains `"status": None`, and a repeat poll records nothing
- [x] 3.5 `tests/test_api_timeseries.py`: stop pre-copying status in the `_obs` helper and the polygon fixture, and assert that `GET /entities` and `GET /entities/{id}` (`latest_properties.status`) carry the normalized status
- [x] 3.6 `tests/test_epb.py` and `tests/test_tnaw.py`: replace the `obs.properties["status"] == ...` assertions with `"status" not in obs.properties` (keep the `obs.status` assertions), and update the comments
- [x] 3.7 Confirm `tests/test_ingest_helpers.py` (fingerprint helpers) needs no change

## 4. Documentation

- [x] 4.1 `AGENTS.md` "Adding a data source": state that a collector sets `NormalizedObservation.status` and ingest records it on the entity (`latest_properties["status"]`) for change detection and serving. Collectors do not copy it into `properties`, and a raw payload `status` key with a different meaning is overridden, so rename it if it must be kept
- [x] 4.2 `AGENTS.md` "The central idea" step 3 (or the data-model bullet for `entities`): note that ingest writes the normalized status into `latest_properties`
- [x] 4.3 Update the `app/ingest.py` module docstring if it describes where status comes from

## 5. Verify

- [x] 5.1 Run the backend test suite and the lint/format checks; all pass
- [x] 5.2 Rebuild and restart via Docker (`sg docker -c 'docker compose up --build -d'`). After two poll cycles, confirm that EPB and TNAW record no new observations for unchanged entities, and that the map's status filter, EPB marker colors, and the detail panel's Status row still show the right values
