"""Unit tests for the retention/prune service, schema migration, and CLI."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from typer.testing import CliRunner
from webreportlog_server import database
from webreportlog_server.cli import app
from webreportlog_server.models import Session as TestSession
from webreportlog_server.models import TestReport
from webreportlog_server.services.retention import prune_database

BASE = datetime(2024, 1, 1, tzinfo=UTC)


@pytest.fixture
def temp_engine(tmp_path, monkeypatch):
    """A file-backed engine wired in as the module's `engine` for the test."""
    db_file = tmp_path / "retention.db"
    engine = create_engine(f"sqlite:///{db_file}")
    monkeypatch.setattr(database, "engine", engine)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed(db: Session, created_at: datetime, payload_kb: int = 200,
          status: str = "completed", reports: int = 1) -> int:
    session = TestSession(status=status, created_at=created_at, updated_at=created_at)
    db.add(session)
    db.commit()
    db.refresh(session)
    half = payload_kb * 1024 // 2
    for i in range(reports):
        db.add(TestReport(
            session_id=session.id, nodeid=f"t.py::test_{session.id}_{i}",
            location=["t.py", 1, "x"], keywords={}, when="call",
            outcome="passed", duration=0.1,
            longrepr="L" * half,
            sections=[["Captured stdout call", "S" * half]],
        ))
    db.commit()
    return session.id


def test_prune_strips_oldest_and_protects_recent(temp_engine):
    with Session(temp_engine) as db:
        ids = [_seed(db, BASE + timedelta(hours=i)) for i in range(5)]
    before = database.get_database_size_bytes()

    with Session(temp_engine) as db:
        report = prune_database(db, max_bytes=500 * 1024, keep_recent=2)

    assert ids[0] in report["stripped"]
    assert ids[3] not in report["stripped"] and ids[4] not in report["stripped"]
    assert report["deleted"] == []
    assert report["under_cap"] is True
    assert database.get_database_size_bytes() < before

    with Session(temp_engine) as db:
        oldest = db.exec(select(TestReport).where(TestReport.session_id == ids[0])).all()
        assert all(r.longrepr is None and r.sections == [] for r in oldest)
        newest = db.exec(select(TestReport).where(TestReport.session_id == ids[4])).all()
        assert all(r.longrepr for r in newest)
        assert db.get(TestSession, ids[0]).logs_pruned is True
        assert db.get(TestSession, ids[4]).logs_pruned is False


def test_prune_deletes_when_stripping_insufficient(temp_engine):
    with Session(temp_engine) as db:
        ids = [_seed(db, BASE + timedelta(hours=i)) for i in range(4)]

    with Session(temp_engine) as db:
        report = prune_database(db, max_bytes=50 * 1024, keep_recent=1)

    # Newest protected; all older sessions deleted entirely.
    assert set(report["deleted"]) == {ids[0], ids[1], ids[2]}
    assert ids[3] not in report["deleted"]
    # Cap unreachable because the single protected session alone exceeds it.
    assert report["under_cap"] is False
    assert report["message"]

    with Session(temp_engine) as db:
        assert db.get(TestSession, ids[3]) is not None
        assert db.get(TestSession, ids[0]) is None


def test_prune_never_touches_in_progress(temp_engine):
    with Session(temp_engine) as db:
        live = _seed(db, BASE, status="in_progress")  # oldest, but live
        _seed(db, BASE + timedelta(hours=1))

    with Session(temp_engine) as db:
        report = prune_database(db, max_bytes=100 * 1024, keep_recent=0)

    assert live not in report["stripped"]
    assert live not in report["deleted"]
    with Session(temp_engine) as db:
        live_reports = db.exec(
            select(TestReport).where(TestReport.session_id == live)
        ).all()
        assert all(r.longrepr for r in live_reports)


def test_prune_noop_when_under_cap(temp_engine):
    with Session(temp_engine) as db:
        _seed(db, BASE, payload_kb=10)

    with Session(temp_engine) as db:
        report = prune_database(db, max_bytes=10 * 1024 * 1024, keep_recent=0)

    assert report["stripped"] == [] and report["deleted"] == []
    assert report["under_cap"] is True


def test_ensure_columns_adds_logs_pruned(tmp_path, monkeypatch):
    db_file = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{db_file}")
    monkeypatch.setattr(database, "engine", engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE session (id INTEGER PRIMARY KEY, status VARCHAR)"
        )

    database.ensure_columns()

    with engine.connect() as conn:
        cols = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(session)").fetchall()
        }
    assert "logs_pruned" in cols
    database.ensure_columns()  # idempotent — must not raise


def test_cli_prune_runs(temp_engine):
    with Session(temp_engine) as db:
        _seed(db, BASE)
        _seed(db, BASE + timedelta(hours=1))

    result = CliRunner().invoke(app, ["prune", "--max-size", "100KB", "--keep-recent", "0"])
    assert result.exit_code == 0, result.output
    assert "Database:" in result.output


def test_cli_prune_requires_cap(temp_engine, monkeypatch):
    monkeypatch.delenv("WEBREPORTLOG_MAX_DB_SIZE", raising=False)
    result = CliRunner().invoke(app, ["prune"])
    assert result.exit_code == 2
    assert "No size cap" in result.output
