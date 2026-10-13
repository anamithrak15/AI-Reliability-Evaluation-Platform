import os

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.auth import passwords
from app.core.config import get_settings
from app.db.database import Base, get_session
from app.main import app


def _test_url():
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return make_url(explicit)
    return make_url(get_settings().database_url).set(database="aireliability_test")


@pytest.fixture(scope="session")
def db_engine():
    url = _test_url()
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except Exception as exc:
        pytest.skip(f"test database unavailable: {exc}")
    finally:
        admin.dispose()

    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    # Tests must not depend on a shared Redis counter; rate-limit tests opt back in.
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", False)


@pytest.fixture
def enqueued(monkeypatch):
    calls = []
    monkeypatch.setattr("app.services.run_service.enqueue_run", lambda run_id: calls.append(run_id))
    return calls


@pytest.fixture
def no_backoff(monkeypatch):
    monkeypatch.setattr(get_settings(), "retry_backoff_seconds", 0.0)


@pytest.fixture
def _db(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def _override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    yield
    app.dependency_overrides.clear()
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with db_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


PASSWORD = "correct horse battery staple"


def new_client(email: str | None = None) -> TestClient:
    """A browser-like client; with an email it registers and keeps that user's session cookie."""
    client = TestClient(app, headers={"X-Requested-With": "fetch"})
    if email:
        resp = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
        assert resp.status_code == 201, resp.text
    return client


@pytest.fixture(autouse=True)
def _cheap_hashing(monkeypatch):
    # Production hashing parameters are deliberately slow; tests only need the same algorithm.
    monkeypatch.setattr(
        passwords, "_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    )


@pytest.fixture(autouse=True)
def _no_demo_seed(monkeypatch):
    # Registration seeds a demo dataset in demo mode; tests that need it opt back in.
    monkeypatch.setattr(get_settings(), "demo_mode", False)


@pytest.fixture
def anonymous_client(_db):
    return new_client()


@pytest.fixture
def client(_db):
    return new_client("user-a@example.com")


@pytest.fixture
def other_client(_db):
    return new_client("user-b@example.com")
