# Web Server Test Suite

This directory contains comprehensive tests for the pytest-webreportlog web service.

## Test Structure

### Part 1: Unit Tests (`test_web_server.py`)
Tests that verify the web server correctly processes JSONL files and displays data.

**Test Fixtures** (`conftest_web.py`):
- `web_server` - Starts FastAPI server on port 8001 for testing
- `api_client` - HTTP client with helper methods
- `simple_passing_jsonl` - Pre-configured JSONL with 1 passing test
- `mixed_outcomes_jsonl` - JSONL with passed/failed/skipped tests
- `setup_teardown_errors_jsonl` - JSONL with setup and teardown errors

**Tests**:

1. **Server Functionality** (2 tests)
   - Server starts and responds
   - Upload rejects invalid files

2. **JSONL Upload & Parsing** (3 tests)
   - Upload simple passing test
   - Upload mixed outcomes
   - Upload setup/teardown errors

3. **Statistics Accuracy** (3 tests)
   - Session API data correctness
   - Sessions list API
   - Session statistics match expectations

4. **HTML Generation** (6 tests)
   - Session HTML contains test names
   - Result labels (PASS/FAIL/ERROR/SKIP) display correctly
   - Tracebacks are properly formatted
   - Setup errors appear as separate entries
   - Teardown errors appear as separate entries
   - Statistics summary displays correctly

### Part 2: Comparison Tests (`test_html_comparison.py`)
Tests that compare our output with pytest-html to ensure compatibility.

**Comparison Utilities**:
- `parse_pytest_html_data()` - Extract test data from pytest-html JSON blob
- `extract_test_results_from_pytest_html()` - Parse pytest-html results
- `extract_our_test_results()` - Parse our HTML results
- `count_results()` - Count result types

**Tests**:

1. **pytest-html Comparison** (3 tests)
   - Compare exception test results with pytest-html
   - Verify teardown error handling matches pytest-html
   - Session statistics match pytest output

2. **Visual Consistency** (3 tests)
   - Traceback formatting structure
   - Result badges use correct colors
   - Collapsed sections are expandable

## Running Tests

```bash
# Run all web server tests
uv run pytest tests/test_web_server.py tests/test_html_comparison.py -v

# Run only unit tests
uv run pytest tests/test_web_server.py -v

# Run only comparison tests
uv run pytest tests/test_html_comparison.py -v

# Run with detailed output
uv run pytest tests/test_web_server.py tests/test_html_comparison.py -vv
```

## Test Coverage

### ✅ JSONL Parsing
- SessionStart/SessionFinish events
- TestReport phases (setup/call/teardown)
- Outcome tracking (passed/failed/skipped/error)
- Traceback formatting from longrepr
- Statistics calculation

### ✅ pytest-html Compatibility
- Same result counts (passed/failed/skipped/errors)
- Setup/teardown errors as separate entries
- Correct outcome labels (FAIL vs ERROR)
- Session statistics match pytest output

### ✅ Web UI Features
- Session list with summary statistics
- Expandable test details
- Formatted tracebacks
- Color-coded result badges
- Captured output display

## Key Verification Points

1. **Statistics Correctness**
   - `total_tests` = unique test count
   - `passed` = tests with call phase passed
   - `failed` = tests with call phase failed
   - `errors` = setup/teardown failures (counted separately)

2. **Display Behavior**
   - Test with passing call + failing teardown → TWO entries:
     - Main test (PASS)
     - Teardown error (ERROR)
   - Setup failure → Single entry (ERROR) with `::setup` suffix
   - Call failure → Single entry (FAIL)

3. **Formatting**
   - Tracebacks preserve pytest's `>` and `E` markers
   - HTML entities properly escaped
   - Monospace font for code sections
   - Color scheme matches result type

## Dependencies

- `requests` - HTTP client for API testing
- `pytest` - Test framework
- Running web server (automatically started via fixture)

## Test Data Location

Pre-configured JSONL fixtures are in `conftest_web.py`. For real pytest runs, tests use `test_sample/test_exceptions.py` to generate reports via subprocess.
