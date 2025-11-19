"""Database models for test sessions and reports."""
from datetime import datetime
from typing import Optional
from enum import Enum
from sqlmodel import Field, SQLModel, Relationship, Column, JSON


class SessionStatus(str, Enum):
    """Session status values."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


class Session(SQLModel, table=True):
    """Test session containing multiple test reports."""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    pytest_version: Optional[str] = None
    exitstatus: Optional[int] = None
    status: str = Field(default=SessionStatus.IN_PROGRESS.value)  # in_progress, completed, interrupted

    # Summary counts
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    xfailed: int = 0  # Expected failures
    xpassed: int = 0  # Unexpected passes
    errors: int = 0

    # Timing
    duration: Optional[float] = None

    # Relationships
    test_reports: list["TestReport"] = Relationship(back_populates="session")


class TestReport(SQLModel, table=True):
    """Individual test report for a specific phase (setup/call/teardown)."""

    id: Optional[int] = Field(default=None, primary_key=True)
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
    start: Optional[float] = None
    stop: Optional[float] = None

    # Details
    longrepr: Optional[str] = None  # Exception/failure details
    sections: list = Field(default_factory=list, sa_column=Column(JSON))  # Captured output
    wasxfail: Optional[str] = None  # For xfail(run=False) tests

    # Relationship
    session: Session = Relationship(back_populates="test_reports")
