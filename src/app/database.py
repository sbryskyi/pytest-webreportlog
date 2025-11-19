"""Database configuration and session management."""
import os
from sqlmodel import SQLModel, create_engine, Session
from pathlib import Path

# Create database directory
DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)

# Get database URL from environment variable or use default
# Format: DATABASE_URL=sqlite:///data/mydb.db or DATABASE_URL=sqlite:///path/to/db.db
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_DIR}/sessions.db")

# Create engine
engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    """Create database tables if they don't exist.

    This preserves existing data - tables are only created if missing.
    """
    # Only create tables if they don't exist (preserves data)
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session for dependency injection."""
    with Session(engine) as session:
        yield session
