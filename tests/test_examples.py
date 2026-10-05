"""The examples are the realistic end-to-end check, so they run as tests.

These need a real TeX toolchain, so they are gated exactly like the other
integration tests. Keeping them here rather than in `test_integration.py` keeps
the distinction clear: those tests pin API behaviour, these pin that the
documented examples still run.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from vectex.fragment import VectexFragment

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SCRIPTS = sorted(EXAMPLES.glob("*.py"))

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("VECTEX_RUN_INTEGRATION") != "1",
        reason="set VECTEX_RUN_INTEGRATION=1 to run external-tool tests",
    ),
]


def _load(script: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(script.stem, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_examples_directory_is_not_empty() -> None:
    """A silent glob miss would turn every test below into a vacuous pass."""
    assert SCRIPTS, f"no example scripts found in {EXAMPLES}"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.stem)
def test_example_runs_and_writes_svg(script: Path, tmp_path: Path) -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    completed = subprocess.run(
        [sys.executable, str(script), "--output-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    written = list(tmp_path.glob("*.svg"))
    assert written, "the example wrote no SVG"
    for path in written:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("<?xml")
        assert "<svg" in text


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.stem)
def test_example_build_returns_fragments(script: Path) -> None:
    """Every example exposes `build()`, which is what the tests reuse."""
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    result = _load(script).build()
    # An example returns either one fragment or a sequence of them.
    fragments = list(result) if isinstance(result, tuple | list) else [result]
    assert fragments
    for fragment in fragments:
        assert isinstance(fragment, VectexFragment)
        assert fragment.width > 0
        assert fragment.height > 0
        assert fragment.to_svg().startswith("<g")


def test_bloch_sphere_crops_to_the_picture() -> None:
    """A full US Letter page here means cropping broke; the sphere is ~163x206."""
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    fragment = _load(EXAMPLES / "bloch_sphere.py").build()
    assert 100 < fragment.width < 300
    assert 100 < fragment.height < 350


def test_bloch_sphere_angles_change_the_drawing() -> None:
    module = _load(EXAMPLES / "bloch_sphere.py")
    assert module.picture(50, 40) != module.picture(30, 40)
    assert r"\def\th{50} \def\ph{40}" in module.picture(50, 40)
