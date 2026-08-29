from __future__ import annotations

import re
from pathlib import Path

import vectex


def test_runtime_version_matches_project_metadata() -> None:
    project_text = (Path(__file__).parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    match = re.search(r'^version = "([^"]+)"$', project_text, re.MULTILINE)

    assert match is not None
    assert vectex.__version__ == match.group(1)
