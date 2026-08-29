from __future__ import annotations

import os
import shutil

import pytest

import vectex

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("VECTEX_RUN_INTEGRATION") != "1",
        reason="set VECTEX_RUN_INTEGRATION=1 to run external-tool tests",
    ),
]


def test_real_pdflatex_and_dvisvgm() -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    fragment = vectex.render(r"E = mc^2", engine="pdflatex")
    assert fragment.width > 0
    assert fragment.to_svg().startswith("<g")


def test_real_typst_and_dvisvgm() -> None:
    if shutil.which("typst") is None or shutil.which("dvisvgm") is None:
        pytest.skip("typst and dvisvgm are required")
    fragment = vectex.render("$ E = m c^2 $", engine="typst")
    assert fragment.width > 0
    assert fragment.to_svg().startswith("<g")
