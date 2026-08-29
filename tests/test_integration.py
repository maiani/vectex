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
    fragment = vectex.render_math(r"E = mc^2", engine="pdflatex")
    assert fragment.width > 0
    assert fragment.width < 100
    assert fragment.height < 100
    assert fragment.baseline is not None
    assert fragment.to_svg().startswith("<g")


def test_real_document_body_mixes_prose_and_mathematics() -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    fragment = vectex.render(r"energy $E = mc^2$", engine="pdflatex")
    assert fragment.width > vectex.render_math(r"E = mc^2").width
    assert fragment.baseline is not None


def test_real_split_and_batch_match_individual_renders() -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    items = [
        vectex.RenderItem("x", math_mode="inline"),
        vectex.RenderItem("g", math_mode="inline"),
        vectex.RenderItem(r"\begin{split}a&=b+c\\&=d\end{split}", math_mode="auto"),
    ]
    batch = vectex.render_many(items)
    individual = tuple(
        vectex.render(item.source, math_mode=item.math_mode) for item in items
    )
    assert [fragment.to_svg() for fragment in batch] == [
        fragment.to_svg() for fragment in individual
    ]
    assert all(fragment.baseline is not None for fragment in batch)


def test_real_batch_mixes_sizes_in_one_compilation() -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    small, large = vectex.render_many(
        [
            vectex.RenderItem("x", size_pt=5, math_mode="inline"),
            vectex.RenderItem("x", size_pt=10, math_mode="inline"),
        ]
    )
    assert large.width == pytest.approx(2 * small.width)
    assert large.baseline == pytest.approx(2 * small.baseline)


def test_real_batch_groups_items_with_their_own_preamble() -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    shared, private = vectex.render_many(
        [
            vectex.RenderItem("$x$", size_pt=7),
            vectex.RenderItem(r"$\bm{n}$", size_pt=7, preamble=r"\usepackage{bm}"),
        ]
    )
    assert shared.width > 0
    assert private.width > 0
    assert (
        private.to_svg()
        == vectex.render(
            vectex.RenderItem(r"$\bm{n}$", size_pt=7, preamble=r"\usepackage{bm}")
        ).to_svg()
    )


def test_real_typst_and_dvisvgm() -> None:
    if shutil.which("typst") is None or shutil.which("dvisvgm") is None:
        pytest.skip("typst and dvisvgm are required")
    fragment = vectex.render("$ E = m c^2 $", engine="typst")
    assert fragment.width > 0
    assert fragment.to_svg().startswith("<g")
