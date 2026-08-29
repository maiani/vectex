from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def complex_svg(fixture_dir: Path) -> bytes:
    return (fixture_dir / "complex.svg").read_bytes()


@pytest.fixture
def simple_svg(fixture_dir: Path) -> bytes:
    return (fixture_dir / "simple.svg").read_bytes()
