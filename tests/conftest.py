"""Shared fixtures for the engine and API test suites."""

from __future__ import annotations

import pytest

from debt_engine.indices import IndexRepository
from tests.helpers import DATA_DIR


@pytest.fixture(scope="session")
def repo() -> IndexRepository:
    return IndexRepository(DATA_DIR)
