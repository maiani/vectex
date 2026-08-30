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


@pytest.mark.parametrize("engine", ["pdflatex", "xelatex", "lualatex"])
def test_real_tex_engines_and_dvisvgm(engine: str) -> None:
    if shutil.which(engine) is None or shutil.which("dvisvgm") is None:
        pytest.skip(f"{engine} and dvisvgm are required")
    fragment = vectex.render(r"$E = mc^2$", engine=engine)
    assert fragment.width > 0
    assert fragment.width < 100
    assert fragment.height < 100
    assert fragment.baseline is not None
    assert fragment.to_svg().startswith("<g")


def test_real_document_body_mixes_prose_and_mathematics() -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    fragment = vectex.render(r"energy $E = mc^2$", engine="pdflatex")
    assert fragment.width > vectex.render(r"$E = mc^2$").width
    assert fragment.baseline is not None


@pytest.mark.parametrize(
    "source",
    [
        r"$$E = mc^2$$",
        r"\[E = mc^2\]",
        r"\begin{align*}E &= mc^2\end{align*}",
    ],
)
def test_real_display_math_bodies(source: str) -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    fragment = vectex.render(source)
    assert fragment.width > 0
    assert fragment.width < 100
    assert fragment.height > 0
    assert fragment.baseline is None


def test_real_split_and_batch_match_individual_renders() -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    items = [
        vectex.RenderItem("$x$"),
        vectex.RenderItem("$g$"),
        vectex.RenderItem(r"$\begin{aligned}a&=b+c\\&=d\end{aligned}$"),
    ]
    batch = vectex.render_many(items)
    individual = tuple(vectex.render(item.source) for item in items)
    assert [fragment.to_svg() for fragment in batch] == [
        fragment.to_svg() for fragment in individual
    ]
    assert all(fragment.baseline is not None for fragment in batch)


def test_real_batch_mixes_sizes_in_one_compilation() -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    small, large = vectex.render_many(
        [
            vectex.RenderItem("$x$", size_pt=5),
            vectex.RenderItem("$x$", size_pt=10),
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
            vectex.RenderItem(r"$\bm{n}$", size_pt=7, extra_packages=("bm",)),
        ]
    )
    assert shared.width > 0
    assert private.width > 0
    assert (
        private.to_svg()
        == vectex.render(
            vectex.RenderItem(r"$\bm{n}$", size_pt=7, extra_packages=("bm",))
        ).to_svg()
    )


def test_real_package_name_convenience() -> None:
    if shutil.which("pdflatex") is None or shutil.which("dvisvgm") is None:
        pytest.skip("pdflatex and dvisvgm are required")
    fragment = vectex.render(r"$\bm{n}$", extra_packages=("bm",))
    assert fragment.width > 0
    assert fragment.metadata["compiler_options"]["extra_packages"] == ["bm"]
