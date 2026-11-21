import pytest
from sqlalchemy import func, select

from app.cli import seed_demo
from app.config import get_settings
from app.models import User

DEMO_PASSWORD = "Demo-Passw0rd"


def _settings(app_env: str):
    # model_construct skips the strict-config validator so 'production' can be simulated.
    base = get_settings().model_dump()
    return type(get_settings()).model_construct(
        **(base | {"app_env": app_env, "demo_marketer_password": DEMO_PASSWORD})
    )


def _count(db) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.phone.like("077000000%")))


@pytest.mark.parametrize("env", ["development", "test", "staging"])
def test_seed_is_idempotent(db, env) -> None:
    assert seed_demo(db, _settings(env)) == 0
    assert seed_demo(db, _settings(env)) == 0
    demo = db.scalars(select(User).where(User.phone == "07700000001")).one()
    assert demo.role == "marketer" and demo.permissions == [] and not demo.must_change_password
    assert _count(db) == 1


def test_seed_refused_in_production(db, capsys) -> None:
    assert seed_demo(db, _settings("production")) == 1
    assert _count(db) == 0
    assert "production" in capsys.readouterr().err


def test_seed_e2e_accounts(db) -> None:
    assert seed_demo(db, _settings("test"), e2e=True) == 0
    users = {u.phone: u for u in db.scalars(select(User).where(User.phone.like("077000000%")))}
    assert set(users) == {"07700000001", "07700000002", "07700000003"}
    assert users["07700000003"].must_change_password is True
    assert users["07700000002"].must_change_password is False
