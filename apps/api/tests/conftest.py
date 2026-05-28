"""
Shared pytest fixtures and configuration for the full test suite.
Provides an in-memory SQLite engine and FastAPI TestClient with DB override.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db

# ─── In-Memory SQLite DB ─────────────────────────────────────────────────────
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """FastAPI dependency override: provides an isolated test database session."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


from app.routers.auth_router import get_current_user_id_dependency
from app.repositories.project_repo import UserRepository
from fastapi import Depends

def override_get_current_user_id(db = Depends(override_get_db)):
    user_repo = UserRepository(db)
    user = user_repo.get_by_email("test@x.com")
    if not user:
        user = user_repo.create("test@x.com", "testpass123", "user")
    return user.id

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user_id_dependency] = override_get_current_user_id


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Session-scoped fixture: creates all DB tables before the test suite and drops them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Function-scoped DB session fixture with automatic rollback for test isolation."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="module")
def client():
    """Module-scoped FastAPI TestClient."""
    with TestClient(app) as c:
        yield c
