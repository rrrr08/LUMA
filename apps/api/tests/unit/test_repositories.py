"""
Unit tests for all repository classes in app.repositories.project_repo

Each class uses a function-scoped rollback db_session from conftest.py
to ensure full test isolation without cross-test state contamination.
"""
import pytest
from app.repositories.project_repo import (
    UserRepository,
    ProjectRepository,
    SourceRepository,
    SchemaRepository,
    ExtractorRepository,
    ApiEndpointRepository,
    ApiKeyRepository,
)
from app.core.security import hash_api_key


# ─── UserRepository ──────────────────────────────────────────────────────────

class TestUserRepository:
    def test_create_user(self, db_session):
        repo = UserRepository(db_session)
        user = repo.create("alice@example.com", "hashedpass", "user")
        assert user.id is not None
        assert user.email == "alice@example.com"
        assert user.role == "user"

    def test_get_by_email_found(self, db_session):
        repo = UserRepository(db_session)
        repo.create("bob@example.com", "hashedpass", "user")
        found = repo.get_by_email("bob@example.com")
        assert found is not None
        assert found.email == "bob@example.com"

    def test_get_by_email_not_found(self, db_session):
        repo = UserRepository(db_session)
        result = repo.get_by_email("nonexistent@example.com")
        assert result is None

    def test_get_by_id_found(self, db_session):
        repo = UserRepository(db_session)
        user = repo.create("charlie@example.com", "pass", "admin")
        found = repo.get_by_id(user.id)
        assert found is not None
        assert found.id == user.id

    def test_get_by_id_not_found(self, db_session):
        repo = UserRepository(db_session)
        result = repo.get_by_id("nonexistent-uuid")
        assert result is None

    def test_default_role_is_user(self, db_session):
        repo = UserRepository(db_session)
        user = repo.create("dave@example.com", "pass")
        assert user.role == "user"


# ─── ProjectRepository ───────────────────────────────────────────────────────

class TestProjectRepository:
    def _make_user(self, db_session, email="proj_user@example.com"):
        user_repo = UserRepository(db_session)
        return user_repo.create(email, "pass", "user")

    def test_create_project(self, db_session):
        user = self._make_user(db_session)
        repo = ProjectRepository(db_session)
        project = repo.create(user.id, "My Project")
        assert project.id is not None
        assert project.name == "My Project"
        assert project.user_id == user.id

    def test_get_by_id_found(self, db_session):
        user = self._make_user(db_session, "proj2@example.com")
        repo = ProjectRepository(db_session)
        project = repo.create(user.id, "Project Alpha")
        found = repo.get_by_id(project.id)
        assert found is not None
        assert found.name == "Project Alpha"

    def test_get_by_id_not_found(self, db_session):
        repo = ProjectRepository(db_session)
        assert repo.get_by_id("nonexistent-id") is None

    def test_get_user_projects_returns_list(self, db_session):
        user = self._make_user(db_session, "proj3@example.com")
        repo = ProjectRepository(db_session)
        repo.create(user.id, "Project One")
        repo.create(user.id, "Project Two")
        projects = repo.get_user_projects(user.id)
        assert len(projects) >= 2

    def test_get_user_projects_empty(self, db_session):
        repo = ProjectRepository(db_session)
        projects = repo.get_user_projects("user-with-no-projects")
        assert projects == []

    def test_update_status(self, db_session):
        user = self._make_user(db_session, "proj4@example.com")
        repo = ProjectRepository(db_session)
        project = repo.create(user.id, "Status Project")
        updated = repo.update_status(project.id, "active")
        assert updated.status == "active"

    def test_update_status_not_found(self, db_session):
        repo = ProjectRepository(db_session)
        result = repo.update_status("nonexistent-id", "active")
        assert result is None


# ─── SourceRepository ────────────────────────────────────────────────────────

class TestSourceRepository:
    def _make_project(self, db_session, email="src_user@example.com"):
        user = UserRepository(db_session).create(email, "pass", "user")
        return ProjectRepository(db_session).create(user.id, "Source Project")

    def test_create_source(self, db_session):
        project = self._make_project(db_session)
        repo = SourceRepository(db_session)
        source = repo.create(project.id, "https://example.com", "example.com")
        assert source.id is not None
        assert source.url == "https://example.com"
        assert source.domain == "example.com"

    def test_get_by_project_id_found(self, db_session):
        project = self._make_project(db_session, "src2@example.com")
        repo = SourceRepository(db_session)
        repo.create(project.id, "https://test.com", "test.com")
        found = repo.get_by_project_id(project.id)
        assert found is not None
        assert found.domain == "test.com"

    def test_get_by_project_id_not_found(self, db_session):
        repo = SourceRepository(db_session)
        assert repo.get_by_project_id("nonexistent-project") is None

    def test_default_robots_status(self, db_session):
        project = self._make_project(db_session, "src3@example.com")
        repo = SourceRepository(db_session)
        source = repo.create(project.id, "https://robots.com", "robots.com")
        assert source.robots_status == "allowed"


# ─── SchemaRepository ────────────────────────────────────────────────────────

class TestSchemaRepository:
    def _make_source(self, db_session, email="schema_user@example.com"):
        user = UserRepository(db_session).create(email, "pass")
        project = ProjectRepository(db_session).create(user.id, "Schema Project")
        return SourceRepository(db_session).create(project.id, "https://schema.com", "schema.com")

    def test_create_schema(self, db_session):
        source = self._make_source(db_session)
        repo = SchemaRepository(db_session)
        schema = repo.create(source.id, {"fields": ["title"]})
        assert schema.id is not None
        assert schema.json_schema == {"fields": ["title"]}

    def test_get_latest_by_source_id(self, db_session):
        source = self._make_source(db_session, "schema2@example.com")
        repo = SchemaRepository(db_session)
        repo.create(source.id, {"version": "v1"}, version=1)
        repo.create(source.id, {"version": "v2"}, version=2)
        latest = repo.get_latest_by_source_id(source.id)
        assert latest is not None
        assert latest.json_schema == {"version": "v2"}

    def test_get_latest_not_found(self, db_session):
        repo = SchemaRepository(db_session)
        assert repo.get_latest_by_source_id("nonexistent-source") is None


# ─── ExtractorRepository ─────────────────────────────────────────────────────

class TestExtractorRepository:
    def _make_schema(self, db_session, email="ext_user@example.com"):
        user = UserRepository(db_session).create(email, "pass")
        project = ProjectRepository(db_session).create(user.id, "Ext Project")
        source = SourceRepository(db_session).create(project.id, "https://ext.com", "ext.com")
        return SchemaRepository(db_session).create(source.id, {"fields": ["price"]})

    def test_create_extractor(self, db_session):
        schema = self._make_schema(db_session)
        repo = ExtractorRepository(db_session)
        extractor = repo.create(schema.id, "async def extract(html, dom): return []")
        assert extractor.id is not None
        assert extractor.is_active is True

    def test_create_deactivates_previous_extractor(self, db_session):
        schema = self._make_schema(db_session, "ext2@example.com")
        repo = ExtractorRepository(db_session)
        extractor_v1 = repo.create(schema.id, "async def extract(html, dom): return [{'v': 1}]", version=1)
        # v1 should be deactivated after creating v2
        repo.create(schema.id, "async def extract(html, dom): return [{'v': 2}]", version=2)
        # Re-query v1
        from app.models.entities import GeneratedExtractor
        v1_reloaded = db_session.query(GeneratedExtractor).filter(
            GeneratedExtractor.id == extractor_v1.id
        ).first()
        assert v1_reloaded.is_active is False

    def test_get_active_by_schema_id(self, db_session):
        schema = self._make_schema(db_session, "ext3@example.com")
        repo = ExtractorRepository(db_session)
        repo.create(schema.id, "async def extract(html, dom): return [{'v': 1}]", version=1)
        repo.create(schema.id, "async def extract(html, dom): return [{'v': 2}]", version=2)
        active = repo.get_active_by_schema_id(schema.id)
        assert active is not None
        assert active.is_active is True
        assert "v': 2" in active.code

    def test_get_active_not_found(self, db_session):
        repo = ExtractorRepository(db_session)
        assert repo.get_active_by_schema_id("nonexistent-schema") is None


# ─── ApiEndpointRepository ───────────────────────────────────────────────────

class TestApiEndpointRepository:
    def _make_project(self, db_session, email="ep_user@example.com"):
        user = UserRepository(db_session).create(email, "pass")
        return ProjectRepository(db_session).create(user.id, "EP Project")

    def test_create_endpoint(self, db_session):
        project = self._make_project(db_session)
        repo = ApiEndpointRepository(db_session)
        endpoint = repo.create(project.id, "/hotels")
        assert endpoint.id is not None
        assert endpoint.path == "/hotels"
        assert endpoint.method == "GET"
        assert endpoint.cache_ttl_sec == 3600

    def test_get_by_path_found(self, db_session):
        project = self._make_project(db_session, "ep2@example.com")
        repo = ApiEndpointRepository(db_session)
        repo.create(project.id, "/flights")
        found = repo.get_by_path("/flights")
        assert found is not None

    def test_get_by_path_not_found(self, db_session):
        repo = ApiEndpointRepository(db_session)
        assert repo.get_by_path("/nonexistent-path") is None

    def test_get_by_project_id(self, db_session):
        project = self._make_project(db_session, "ep3@example.com")
        repo = ApiEndpointRepository(db_session)
        repo.create(project.id, "/cars")
        found = repo.get_by_project_id(project.id)
        assert found is not None
        assert found.path == "/cars"

    def test_get_by_project_id_not_found(self, db_session):
        repo = ApiEndpointRepository(db_session)
        assert repo.get_by_project_id("nonexistent-project") is None


# ─── ApiKeyRepository ────────────────────────────────────────────────────────

class TestApiKeyRepository:
    def _make_user(self, db_session, email="key_user@example.com"):
        return UserRepository(db_session).create(email, "pass", "user")

    def test_create_api_key(self, db_session):
        user = self._make_user(db_session)
        repo = ApiKeyRepository(db_session)
        key = repo.create(user.id, "sk_live_testtoken123", "My Key")
        assert key.id is not None
        assert key.name == "My Key"
        # key_hash should be the SHA256 hash, not the raw key
        assert key.key_hash == hash_api_key("sk_live_testtoken123")

    def test_get_by_hash_found(self, db_session):
        user = self._make_user(db_session, "key2@example.com")
        repo = ApiKeyRepository(db_session)
        raw_key = "sk_live_unique_key_abc"
        repo.create(user.id, raw_key, "Test Key")
        found = repo.get_by_hash(hash_api_key(raw_key))
        assert found is not None
        assert found.name == "Test Key"

    def test_get_by_hash_not_found(self, db_session):
        repo = ApiKeyRepository(db_session)
        assert repo.get_by_hash("nonexistent-hash") is None

    def test_get_user_keys(self, db_session):
        user = self._make_user(db_session, "key3@example.com")
        repo = ApiKeyRepository(db_session)
        repo.create(user.id, "sk_live_key_one", "Key 1")
        repo.create(user.id, "sk_live_key_two", "Key 2")
        keys = repo.get_user_keys(user.id)
        assert len(keys) >= 2

    def test_get_user_keys_empty(self, db_session):
        repo = ApiKeyRepository(db_session)
        keys = repo.get_user_keys("user-with-no-keys")
        assert keys == []
