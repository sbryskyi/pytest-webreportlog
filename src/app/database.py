"""Database configuration and session management."""
from sqlmodel import SQLModel, create_engine, Session
from pathlib import Path

# Create database directory
DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)

# SQLite database path
DATABASE_URL = f"sqlite:///{DB_DIR}/sessions.db"

# Create engine
engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    """Create database tables."""
    # Drop all tables first to handle schema changes
    # This is acceptable for dev/testing - in production you'd use migrations
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session for dependency injection."""
    with Session(engine) as session:
        yield session
