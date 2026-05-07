#!/bin/sh
set -e

# Wait for the database to be reachable before running migrations.
if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
    echo "Waiting for database at $DB_HOST:$DB_PORT ..."
    until nc -z "$DB_HOST" "$DB_PORT"; do
        sleep 1
    done
    echo "Database is up."
fi

# Apply migrations and collect static files. Both are idempotent.
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
