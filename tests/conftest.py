import pytest
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    """
    Fixture to run tests within a Prefect test harness, providing an isolated
    temporary local SQLite database for Prefect operations.
    This fixture is automatically applied to all tests in the 'tests' directory
    and its subdirectories due to its placement in conftest.py and 'autouse=True'.
    """
    with prefect_test_harness():
        yield
