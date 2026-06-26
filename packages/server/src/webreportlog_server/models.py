"""Database models for test sessions and reports."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, ForeignKey, Integer
from sqlmodel import Field, Relationship, SQLModel

from .utils import get_current_utc_time


class SessionStatus(StrEnum):
    """Session status values."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


class TestPhase(StrEnum):
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
    xfailed: int = 0
    xpassed: int = 0
    errors: int = 0

    # Timing
    duration: float | None = None

    # Retention: True when this session's logs/tracebacks were stripped to reclaim space
    logs_pruned: bool = Field(default=False)

    # Environment metadata collected by the plugin at session start
    env_metadata: dict | None = Field(default=None, sa_column=Column(JSON))

    # Relationships
    test_reports: list["TestReport"] = Relationship(back_populates="session")


class TestReport(SQLModel, table=True):
    """Individual test report for a specific phase (setup/call/teardown)."""

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("session.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    # Test identification — indexed for frequent WHERE/GROUP BY usage
    nodeid: str = Field(index=True)
    location: list = Field(sa_column=Column(JSON))
    keywords: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Phase and outcome — indexed for frequent WHERE filtering
    when: str = Field(index=True)
    outcome: str

    # Timing
    duration: float = 0.0
    start: float | None = None
    stop: float | None = None

    # Details
    longrepr: str | None = None
    sections: list = Field(default_factory=list, sa_column=Column(JSON))
    wasxfail: str | None = None

    # Relationship
    session: Session = Relationship(back_populates="test_reports")
