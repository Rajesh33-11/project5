import os

import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    url = os.environ.get("BASE_URL")
    if not url:
        pytest.exit("BASE_URL env var is required (Jenkins injects it from the e2e-base-url credential)")
    return url.rstrip("/")
