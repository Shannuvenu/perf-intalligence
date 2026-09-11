"""
Shared pytest fixtures. Tests run against an isolated on-disk SQLite DB
(fast, zero external dependency) rather than Postgres - the PortableJSON
column type (see app/db/types.py) is what makes this possible without
diverging from production model definitions.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_perf_intelligence.db"
os.environ["ENV"] = "test"
os.environ["PSI_PROVIDER"] = "mock"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["STORAGE_LOCAL_ROOT"] = "./test_storage/raw"
os.environ["SCHEDULER_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.site import Site
from app.models.url import Url

TEST_DB_PATH = "./test_perf_intelligence.db"
TEST_ENGINE = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=TEST_ENGINE)
    Base.metadata.create_all(bind=TEST_ENGINE)
    get_settings.cache_clear()
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def site(db_session):
    s = Site(name="Deccan Herald", base_url="https://www.deccanherald.com/")
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture
def url(db_session, site):
    u = Url(site_id=site.site_id, url="https://www.deccanherald.com/", url_category="homepage", enabled=True)
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u
