"""Database engine and per-request session dependency (sync SQLAlchemy 2 + psycopg 3)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # A database error's text reaches the logs through the server's traceback: never with its
    # values (names, phones, SAS usernames; Principle II, specs/015 T054).
    return create_engine(get_settings().database_url, pool_pre_ping=True, hide_parameters=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
