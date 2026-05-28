import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, ForeignKey, DateTime, Float, Integer, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")
    plan = Column(String, default="free")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, default="active")  # active, paused, broken
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="projects")
    sources = relationship("Source", back_populates="project", cascade="all, delete-orphan")
    endpoints = relationship("ApiEndpoint", back_populates="project", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    url = Column(String, nullable=False)
    url_template = Column(String, nullable=True)
    proxy_enabled = Column(Boolean, default=False)
    proxy_country = Column(String, nullable=True)
    domain = Column(String, nullable=False, index=True)
    robots_status = Column(String, default="allowed")  # allowed, disallowed, unchecked
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="sources")
    schemas = relationship("Schema", back_populates="source", cascade="all, delete-orphan")


class Schema(Base):
    __tablename__ = "schemas"

    id = Column(String, primary_key=True, default=generate_uuid)
    source_id = Column(String, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    json_schema = Column(JSON, nullable=False)
    confidence_score = Column(Float, default=0.0)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    source = relationship("Source", back_populates="schemas")
    extractors = relationship("GeneratedExtractor", back_populates="schema", cascade="all, delete-orphan")


class GeneratedExtractor(Base):
    __tablename__ = "generated_extractors"

    id = Column(String, primary_key=True, default=generate_uuid)
    schema_id = Column(String, ForeignKey("schemas.id", ondelete="CASCADE"), nullable=False)
    code = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    schema = relationship("Schema", back_populates="extractors")


class ApiEndpoint(Base):
    __tablename__ = "api_endpoints"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    path = Column(String, unique=True, nullable=False, index=True)
    method = Column(String, default="GET")
    cache_ttl_sec = Column(Integer, default=3600)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="endpoints")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="api_keys")


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    endpoint_id = Column(String, ForeignKey("api_endpoints.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status_code = Column(Integer, nullable=False)
    cache_status = Column(String, nullable=False)  # HIT, MISS, FALLBACK-STALE
    response_time_ms = Column(Float, nullable=False)

    endpoint = relationship("ApiEndpoint")
    user = relationship("User")


class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    url = Column(String, nullable=False)
    trigger_type = Column(String, default="on_change")  # on_change, on_new_item, on_failure
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    project = relationship("Project")


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    google_sheet_url = Column(String, nullable=True)
    google_sheet_sync_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    project = relationship("Project")


class UserInvoice(Base):
    __tablename__ = "user_invoices"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invoice_number = Column(String, unique=True, nullable=False)
    plan = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default="paid")  # paid, open, voided
    billing_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User")


class UserQuotaSettings(Base):
    __tablename__ = "user_quota_settings"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    email_alerts_enabled = Column(Boolean, default=True)
    slack_alerts_enabled = Column(Boolean, default=False)
    slack_webhook_url = Column(String, nullable=True)
    threshold_percentage = Column(Integer, default=80)

    user = relationship("User")


