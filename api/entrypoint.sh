#!/usr/bin/env sh
set -e

# Apply migrations before serving, when the host has no separate release step.
#
# Fly runs `alembic upgrade head` as a release command, which is better: a
# failed migration aborts the deploy and the old version keeps serving. Render's
# free plan has no pre-deploy hook, so the same job happens here instead. One
# instance runs on the free plan, so there is no second process to race with.
if [ "${RUN_MIGRATIONS_ON_START:-false}" = "true" ]; then
  echo "running migrations"
  alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
