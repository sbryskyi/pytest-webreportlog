"""Database models for test sessions and reports."""
from datetime import datetime
from enum import Enum
from sqlmodel import Field, SQLModel, Relationship, Column, JSON
from .utils import get_current_utc_time


class SessionStatus(str, Enum):
    """Session status values."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


class TestPhase(str, Enum):
    """Test execution phase values."""
    SETUP = "setup"
    CALL = "call"
    TEARDOWN = "teardown"


class Session(SQLModel, table=True):
    """Test session containing multiple test reports."""

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_current_utc_time)
    updated_at: datetime = Field(default_factory=get_current_utc_time)
    pytest_version: str | None = None
    exitstatus: int | None = None
    status: str = Field(default=SessionStatus.IN_PROGRESS.value)

    # Summary counts
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    xfailed: int = 0  # Expected failures
    xpassed: int = 0  # Unexpected passes
    errors: int = 0

    # Timing
    duration: float | None = None

    # Relationships
    test_reports: list["TestReport"] = Relationship(back_populates="session")


class TestReport(SQLModel, table=True):
    """Individual test report for a specific phase (setup/call/teardown)."""

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="session.id")

    # Test identification
    nodeid: str
    location: list = Field(sa_column=Column(JSON))  # [file, line, test_name]
    keywords: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Phase and outcome
    when: str  # setup, call, or teardown
    outcome: str  # passed, failed, skipped, error

    # Timing
    duration: float = 0.0
    start: float | None = None
    stop: float | None = None

    # Details
    longrepr: str | None = None  # Exception/failure details
    sections: list = Field(default_factory=list, sa_column=Column(JSON))  # Captured output
    wasxfail: str | None = None  # For xfail(run=False) tests

    # Relationship
    session: Session = Relationship(back_populates="test_reports")
