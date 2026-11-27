import pytest

from benchmarks.offline import offline_runtime


@pytest.fixture(autouse=True)
def offline():
    with offline_runtime():
        yield
