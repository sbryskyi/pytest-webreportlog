"""Unit tests for database-size formatting and parsing."""

import pytest
from webreportlog_server.utils import format_size, parse_size


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2048", 2048),
        ("1KB", 1024),
        ("1 kb", 1024),
        ("500MB", 500 * 1024**2),
        ("1.5G", int(1.5 * 1024**3)),
        ("2GB", 2 * 1024**3),
        ("3 GiB", 3 * 1024**3),
        ("10", 10),
        (4096, 4096),
    ],
)
def test_parse_size(text, expected: int) -> None:
    assert parse_size(text) == expected


@pytest.mark.parametrize("bad", ["", "abc", "GB", "1.2.3MB", "-5", "5 PB"])
def test_parse_size_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_size(bad)


@pytest.mark.parametrize(
    "num_bytes,expected",
    [
        (None, "n/a"),
        (0, "0 B"),
        (512, "512 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1024 * 1024, "1.0 MB"),
        (int(2.5 * 1024 * 1024), "2.5 MB"),
        (1024**3, "1.0 GB"),
        (1024**4, "1.0 TB"),
    ],
)
def test_format_size(num_bytes: int | None, expected: str) -> None:
    assert format_size(num_bytes) == expected
