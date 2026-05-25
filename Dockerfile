# syntax=docker/dockerfile:1.7

# ---------- Stage 1: builder ----------
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps for mysqlclient, lxml, Pillow, cryptography wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        default-libmysqlclient-dev \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        zlib1g-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt


# ---------- Stage 2: runtime ----------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=daycareSystem.settings

# Runtime shared libs only (no -dev packages).
RUN apt-get update && apt-get install -y --no-install-recommends \
        default-libmysqlclient-dev \
        libxml2 \
        libxslt1.1 \
        libjpeg62-turbo \
        zlib1g \
        libffi8 \
        netcat-openbsd \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user.
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --create-home --home-dir /home/app app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy source. .dockerignore keeps .env, .git, __pycache__, etc. out.
COPY --chown=app:app . /app

# Pre-create writable dirs and make the entrypoint executable.
# (Windows filesystems do not preserve the +x bit through COPY.)
RUN mkdir -p /app/staticfiles /app/media /app/media/enrollment_forms /app/media/qr /app/media/child_images \
    && chmod +x /app/entrypoint.sh \
    && chown -R app:app /app

USER app

# Bake static files into the image so containers boot fast.
# Dummy env values let settings.py load; collectstatic does not hit the DB.
RUN SECRET_KEY=build-time-dummy DEBUG=False \
    DB_NAME=x DB_USER=x DB_PASSWORD=x DB_HOST=x DB_PORT=3306 \
    PROD_URL=https://example.invalid/ QR_METHOD_NAME=checkInView \
    python manage.py collectstatic --noinput --clear

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "daycareSystem.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
