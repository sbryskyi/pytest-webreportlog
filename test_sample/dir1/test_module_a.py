import pytest
import logging
import time


@pytest.fixture
def setup_teardown():
    print("Setup print")
    time.sleep(0.11)
    logging.warning("Setup log")
    yield
    print("Teardown print")
    time.sleep(0.12)
    logging.warning("Teardown log")


def test_pass(setup_teardown):
    print("Call print")
    time.sleep(0.13)
    logging.warning("Call log")

