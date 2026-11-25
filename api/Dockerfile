FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# INSTALL_DEV=true adds test/lint tools (used by docker-compose.override.yml only).
ARG INSTALL_DEV=false

# Backup tools (specs/016 research R1): pg_dump/pg_restore 16 matching the database server, from the
# PostgreSQL apt repository (Debian's own client is a newer major), and age for encryption.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 age \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN python -c "import tomllib,os; d=tomllib.load(open('pyproject.toml','rb'))['project']; \
deps=d['dependencies']+(d['optional-dependencies']['dev'] if os.environ.get('INSTALL_DEV')=='true' else []); \
open('/tmp/requirements.txt','w').write('\n'.join(deps))" \
    && pip install -r /tmp/requirements.txt

# /data/uploads: private card-image storage (specs/005 research.md R7). A new named volume
# mounted there inherits this owner, so the app user can write to it.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data/uploads && chown app:app /data/uploads && chmod 700 /data/uploads

COPY --chown=app:app . .
RUN chmod +x /app/entrypoint.sh

USER app
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
