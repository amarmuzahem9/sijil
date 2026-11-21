FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# INSTALL_DEV=true adds test/lint tools (used by docker-compose.override.yml only).
ARG INSTALL_DEV=false

COPY pyproject.toml ./
RUN python -c "import tomllib,os; d=tomllib.load(open('pyproject.toml','rb'))['project']; \
deps=d['dependencies']+(d['optional-dependencies']['dev'] if os.environ.get('INSTALL_DEV')=='true' else []); \
open('/tmp/requirements.txt','w').write('\n'.join(deps))" \
    && pip install -r /tmp/requirements.txt

RUN useradd --create-home --uid 10001 app

COPY --chown=app:app . .
RUN chmod +x /app/entrypoint.sh

USER app
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
