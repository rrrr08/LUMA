from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.entities import User, Project, Source, Schema, GeneratedExtractor, ApiEndpoint, ApiKey, RequestLog
from app.core.security import hash_api_key

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, email: str, hashed_password: str, role: str = "user") -> User:
        user = User(email=email, hashed_password=hashed_password, role=role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, project_id: str) -> Optional[Project]:
        return self.db.query(Project).filter(Project.id == project_id).first()

    def get_user_projects(self, user_id: str) -> List[Project]:
        return self.db.query(Project).filter(Project.user_id == user_id).all()

    def create(self, user_id: str, name: str) -> Project:
        project = Project(user_id=user_id, name=name)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update_status(self, project_id: str, status: str) -> Optional[Project]:
        project = self.get_by_id(project_id)
        if project:
            project.status = status
            self.db.commit()
            self.db.refresh(project)
        return project

    def delete(self, project_id: str, user_id: str) -> bool:
        project = self.db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
        if project:
            self.db.delete(project)
            self.db.commit()
            return True
        return False


class SourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, project_id: str, url: str, domain: str, robots_status: str = "allowed") -> Source:
        source = Source(project_id=project_id, url=url, domain=domain, robots_status=robots_status)
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def get_by_project_id(self, project_id: str) -> Optional[Source]:
        return self.db.query(Source).filter(Source.project_id == project_id).first()


class SchemaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, source_id: str, json_schema: dict, confidence_score: float = 0.0, version: int = 1) -> Schema:
        schema_obj = Schema(source_id=source_id, json_schema=json_schema, confidence_score=confidence_score, version=version)
        self.db.add(schema_obj)
        self.db.commit()
        self.db.refresh(schema_obj)
        return schema_obj

    def get_latest_by_source_id(self, source_id: str) -> Optional[Schema]:
        return self.db.query(Schema).filter(Schema.source_id == source_id).order_by(Schema.version.desc()).first()


class ExtractorRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, schema_id: str, code: str, version: int = 1) -> GeneratedExtractor:
        extractor = GeneratedExtractor(schema_id=schema_id, code=code, version=version, is_active=True)
        # Deactivate previous extractors for this schema
        self.db.query(GeneratedExtractor).filter(
            GeneratedExtractor.schema_id == schema_id
        ).update({"is_active": False})
        
        self.db.add(extractor)
        self.db.commit()
        self.db.refresh(extractor)
        return extractor

    def get_active_by_schema_id(self, schema_id: str) -> Optional[GeneratedExtractor]:
        return self.db.query(GeneratedExtractor).filter(
            GeneratedExtractor.schema_id == schema_id,
            GeneratedExtractor.is_active == True
        ).first()


class ApiEndpointRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, project_id: str, path: str, method: str = "GET", cache_ttl_sec: int = 3600) -> ApiEndpoint:
        endpoint = ApiEndpoint(project_id=project_id, path=path, method=method, cache_ttl_sec=cache_ttl_sec)
        self.db.add(endpoint)
        self.db.commit()
        self.db.refresh(endpoint)
        return endpoint

    def get_by_path(self, path: str) -> Optional[ApiEndpoint]:
        return self.db.query(ApiEndpoint).filter(ApiEndpoint.path == path).first()

    def get_by_project_id(self, project_id: str) -> Optional[ApiEndpoint]:
        return self.db.query(ApiEndpoint).filter(ApiEndpoint.project_id == project_id).first()


class ApiKeyRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: str, raw_key: str, name: str) -> ApiKey:
        key_hash = hash_api_key(raw_key)
        api_key = ApiKey(user_id=user_id, key_hash=key_hash, name=name)
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def get_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        return self.db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()

    def get_user_keys(self, user_id: str) -> List[ApiKey]:
        return self.db.query(ApiKey).filter(ApiKey.user_id == user_id).all()

    def delete(self, key_id: str, user_id: str) -> bool:
        key_obj = self.db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user_id).first()
        if key_obj:
            self.db.delete(key_obj)
            self.db.commit()
            return True
        return False


class RequestLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_summary_by_user(self, user_id: str) -> dict:
        from datetime import datetime, timedelta, timezone
        
        # Total requests
        total_requests = self.db.query(RequestLog).filter(RequestLog.user_id == user_id).count()

        # Requests this month (last 30 days)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        requests_this_month = self.db.query(RequestLog).filter(
            RequestLog.user_id == user_id,
            RequestLog.requested_at >= thirty_days_ago
        ).count()

        # Cache hit rate (HIT / total_requests)
        hits = self.db.query(RequestLog).filter(
            RequestLog.user_id == user_id,
            RequestLog.cache_status == "HIT"
        ).count()
        cache_hit_rate = (hits / total_requests) if total_requests > 0 else 0.0

        # Avg response time
        avg_res = self.db.query(func.avg(RequestLog.response_time_ms)).filter(
            RequestLog.user_id == user_id
        ).scalar()
        avg_response_ms = float(avg_res) if avg_res is not None else 0.0

        # Crawl success rate (status < 500 / total_requests)
        successful_requests = self.db.query(RequestLog).filter(
            RequestLog.user_id == user_id,
            RequestLog.status_code < 500
        ).count()
        crawl_success_rate = (successful_requests / total_requests) if total_requests > 0 else 1.0

        # Active endpoints count (endpoints belonging to active projects of user)
        active_endpoints = self.db.query(ApiEndpoint).join(Project).filter(
            Project.user_id == user_id,
            Project.status == "active"
        ).count()

        return {
            "total_requests": total_requests,
            "requests_this_month": requests_this_month,
            "cache_hit_rate": cache_hit_rate,
            "avg_response_ms": avg_response_ms,
            "crawl_success_rate": crawl_success_rate,
            "active_endpoints": active_endpoints
        }

    def get_per_endpoint(self, user_id: str) -> list:
        # Group by endpoint, return count and last hit timestamp
        results = self.db.query(
            RequestLog.endpoint_id,
            func.count(RequestLog.id).label("request_count"),
            func.max(RequestLog.requested_at).label("last_hit"),
            ApiEndpoint.path
        ).join(ApiEndpoint).filter(
            RequestLog.user_id == user_id
        ).group_by(
            RequestLog.endpoint_id,
            ApiEndpoint.path
        ).all()

        return [
            {
                "endpoint_id": r.endpoint_id,
                "path": r.path,
                "request_count": r.request_count,
                "last_hit": r.last_hit.isoformat() if r.last_hit else None
            }
            for r in results
        ]
