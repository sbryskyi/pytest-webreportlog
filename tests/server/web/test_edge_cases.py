"""Tests for edge cases and boundary conditions."""
from .conftest import APIClient
from .jsonl_builder import JSONLBuilder, simple_test, xfail_test


def test_jsonl_builder_simple_test(api_client: APIClient) -> None:
    """Test that JSONLBuilder creates valid simple test JSONL."""
    jsonl = simple_test("test.py::test_one", outcome="passed")

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1
    assert result["passed"] == 1


def test_jsonl_builder_failed_test(api_client: APIClient) -> None:
    """Test that JSONLBuilder creates valid failed test JSONL."""
    jsonl = simple_test("test.py::test_fail", outcome="failed")

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1
    assert result["failed"] == 1


def test_jsonl_builder_xfail_test(api_client: APIClient) -> None:
    """Test that JSONLBuilder creates valid xfail test JSONL."""
    jsonl = xfail_test("test.py::test_xfail", passes=False)

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1
    assert result["xfailed"] == 1


def test_jsonl_builder_xpass_test(api_client: APIClient) -> None:
    """Test that JSONLBuilder creates valid xpass test JSONL."""
    jsonl = xfail_test("test.py::test_xpass", passes=True)

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1
    assert result["xpassed"] == 1


def test_jsonl_builder_multiple_tests(api_client: APIClient) -> None:
    """Test that JSONLBuilder handles multiple tests correctly."""
    builder = JSONLBuilder()
    jsonl = (
        builder.session_start()
        .test("test.py::test_one")
        .setup()
        .call(outcome="passed")
        .teardown()
        .test("test.py::test_two")
        .setup()
        .call(outcome="failed", longrepr={"reprcrash": {"message": "Error"}})
        .teardown()
        .test("test.py::test_three")
        .setup()
        .call(outcome="skipped")
        .teardown()
        .session_finish(exitstatus=1)
        .build()
    )

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 3
    assert result["passed"] == 1
    assert result["failed"] == 1
    assert result["skipped"] == 1


def test_jsonl_builder_with_sections(api_client: APIClient) -> None:
    """Test that JSONLBuilder handles captured output sections."""
    builder = JSONLBuilder()
    jsonl = (
        builder.session_start()
        .test("test.py::test_with_output")
        .setup(sections=[["Captured stdout setup", "Setup output"]])
        .call(
            outcome="passed",
            sections=[["Captured stdout call", "Test output"]],
        )
        .teardown(sections=[["Captured stdout teardown", "Teardown output"]])
        .session_finish()
        .build()
    )

    result = api_client.stream_jsonl(jsonl)
    session_id = result["session_id"]

    html = api_client.get_session_html(session_id)

    assert "Setup output" in html
    assert "Test output" in html
    assert "Teardown output" in html


def test_very_long_nodeid(api_client: APIClient) -> None:
    """Test handling of extremely long node IDs."""
    # Create a nodeid with many parameterized values
    long_nodeid = (
        "test_module.py::TestClass::test_method["
        + "-".join([f"param{i}" for i in range(50)])
        + "]"
    )
    jsonl = simple_test(long_nodeid, outcome="passed")

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1


def test_unicode_in_nodeid(api_client: APIClient) -> None:
    """Test handling of Unicode characters in node IDs."""
    jsonl = simple_test("test_módulo.py::test_función_básica", outcome="passed")

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1


def test_unicode_in_output(api_client: APIClient) -> None:
    """Test handling of Unicode characters in captured output."""
    builder = JSONLBuilder()
    jsonl = (
        builder.session_start()
        .test("test.py::test_unicode")
        .setup()
        .call(
            outcome="passed",
            sections=[["Captured stdout call", "你好世界 🎉 مرحبا"]],
        )
        .teardown()
        .session_finish()
        .build()
    )

    result = api_client.stream_jsonl(jsonl)
    session_id = result["session_id"]

    html = api_client.get_session_html(session_id)

    assert "你好世界" in html
    assert "🎉" in html
    assert "مرحبا" in html


def test_many_tests_in_session(api_client: APIClient) -> None:
    """Test handling of sessions with many tests."""
    builder = JSONLBuilder()
    builder.session_start()

    # Create 50 tests
    for i in range(50):
        outcome = "passed" if i % 3 != 0 else "failed"
        test = builder.test(f"test.py::test_{i:03d}").setup()
        if outcome == "passed":
            test.call(outcome="passed")
        else:
            test.call(
                outcome="failed", longrepr={"reprcrash": {"message": f"Error {i}"}}
            )
        test.teardown()

    jsonl = builder.session_finish(exitstatus=1).build()

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 50
    assert result["failed"] == 17  # Every 3rd test fails (0, 3, 6, ..., 48)


def test_session_with_only_setup_errors(api_client: APIClient) -> None:
    """Test session where all tests fail in setup phase."""
    builder = JSONLBuilder()
    jsonl = (
        builder.session_start()
        .test("test.py::test_one")
        .setup(
            outcome="failed",
            longrepr={"reprcrash": {"message": "Fixture failed"}},
        )
        .test("test.py::test_two")
        .setup(
            outcome="failed",
            longrepr={"reprcrash": {"message": "Fixture failed"}},
        )
        .session_finish(exitstatus=1)
        .build()
    )

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 2
    assert result["errors"] == 2
    assert result["passed"] == 0


def test_session_with_only_teardown_errors(api_client: APIClient) -> None:
    """Test session where all tests have teardown errors."""
    builder = JSONLBuilder()
    jsonl = (
        builder.session_start()
        .test("test.py::test_one")
        .setup()
        .call(outcome="passed")
        .teardown(
            outcome="failed",
            longrepr={"reprcrash": {"message": "Cleanup failed"}},
        )
        .test("test.py::test_two")
        .setup()
        .call(outcome="passed")
        .teardown(
            outcome="failed",
            longrepr={"reprcrash": {"message": "Cleanup failed"}},
        )
        .session_finish(exitstatus=1)
        .build()
    )

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 2
    assert result["passed"] == 2  # Call phases passed
    assert result["errors"] == 2  # Teardown errors


def test_empty_session_no_tests(api_client: APIClient) -> None:
    """Test uploading a session with no tests."""
    builder = JSONLBuilder()
    jsonl = builder.session_start().session_finish(exitstatus=0).build()

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 0


def test_zero_duration_tests(api_client: APIClient) -> None:
    """Test handling of tests with zero duration."""
    builder = JSONLBuilder()
    jsonl = (
        builder.session_start()
        .test("test.py::test_instant")
        .setup(duration=0.0)
        .call(outcome="passed", duration=0.0)
        .teardown(duration=0.0)
        .session_finish()
        .build()
    )

    result = api_client.stream_jsonl(jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1
