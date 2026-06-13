#!/bin/sh
set -e

# The db service is gated by a healthcheck (compose waits for it), so by the time
# we get here Postgres is accepting connections. Apply migrations, then serve.
echo "Applying database migrations…"
alembic upgrade head

echo "Starting LocalDash…"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
