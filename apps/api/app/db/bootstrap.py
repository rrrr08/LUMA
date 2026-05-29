import logging
from sqlalchemy import inspect
from app.db.session import engine
from app.db.init_db import init_db
from alembic.config import Config
from alembic import command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bootstrap")

def bootstrap() -> None:
    """
    Bootstraps the database safely:
    - If the database is new (no alembic_version table), it creates all schemas and stamps it to head.
    - If the database is existing, it runs alembic upgrade head to apply incremental migrations.
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    # If the alembic_version table does not exist, this is a clean database bootstrap
    if "alembic_version" not in table_names:
        logger.info("No alembic_version table found. Bootstrapping new database...")
        # Create all tables from SQLAlchemy models
        init_db()
        
        # Stamp database to the current head of migrations
        alembic_cfg = Config("alembic.ini")
        command.stamp(alembic_cfg, "head")
        logger.info("Database bootstrap and stamp to head completed successfully.")
    else:
        logger.info("alembic_version table found. Applying pending database migrations...")
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully.")

if __name__ == "__main__":
    bootstrap()
