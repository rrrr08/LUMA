from app.db.session import engine, Base
from app.models.entities import User, Project, Source, Schema, GeneratedExtractor, ApiEndpoint, ApiKey, WebhookConfig, IntegrationConfig

def init_db() -> None:
    """
    Initializes the database.
    Database migrations are handled via Alembic in production/development.
    """
    Base.metadata.create_all(bind=engine)


