import logging
from sqlalchemy import inspect, text
from app.db.session import engine
from app.db.init_db import init_db
from alembic.config import Config
from alembic import command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bootstrap")

def bootstrap() -> None:
    """
    Bootstraps the database safely:
    - If the database has no migration stamp (no alembic_version or empty alembic_version),
      it creates all schemas and stamps it to head.
    - If the database is already stamped, it runs alembic upgrade head to apply incremental migrations.
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    has_stamp = False
    if "alembic_version" in table_names:
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT count(*) FROM alembic_version")).scalar()
                if res and res > 0:
                    has_stamp = True
        except Exception as e:
            logger.warning(f"Failed to query alembic_version table: {e}. Defaulting to unstamped.")
            has_stamp = False

    # If the database is not stamped, initialize tables and stamp to head
    if not has_stamp:
        logger.info("Database has no migration stamp. Initializing schemas & stamping to head...")
        # Create all tables from SQLAlchemy models (does nothing for tables that already exist)
        init_db()
        
        # Stamp database to the current head of migrations
        alembic_cfg = Config("alembic.ini")
        command.stamp(alembic_cfg, "head")
        logger.info("Database bootstrap and stamp to head completed successfully.")
    else:
        logger.info("Database migration stamp found. Applying pending database migrations...")
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully.")

if __name__ == "__main__":
    bootstrap()
