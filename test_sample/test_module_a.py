import pytest
import logging

@pytest.fixture
def setup_teardown():
    print("Setup print")
    logging.warning("Setup log")
    yield
    print("Teardown print")
    logging.warning("Teardown log")


def test_pass(setup_teardown):
    print("Call print")
    logging.warning("Call log")

