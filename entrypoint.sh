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

# Apply migrations. Static files are baked into the image at build time.
python manage.py migrate --noinput

exec "$@"
