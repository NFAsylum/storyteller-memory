import pytest


def pytest_sessionfinish(session, exitstatus):
    # An empty test suite (bootstrap phase) must not fail CI: pytest returns
    # exit code 5 (NO_TESTS_COLLECTED) with zero tests, so remap it to success.
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
