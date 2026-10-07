from __future__ import annotations

import drawsvg
import svg

from vectex import Normalizer


def fragment(simple_svg: bytes):
    return Normalizer().normalize(
        simple_svg,
        source="x",
        engine="pdflatex",
        converter="dvisvgm",
        id_prefix="adapter",
    )


def test_svg_py_adapter_uses_backend_serialization(simple_svg: bytes) -> None:
    rendered = fragment(simple_svg)
    element = rendered.to_svg_py()
    assert isinstance(element, svg.Element)
    assert str(element) == rendered.to_svg()


def test_svg_py_wrappers_compare_by_content(simple_svg: bytes) -> None:
    rendered = fragment(simple_svg)
    other = Normalizer().normalize(
        simple_svg,
        source="x",
        engine="pdflatex",
        converter="dvisvgm",
        id_prefix="other",
    )
    # Wrappers from separate calls are one type, equal exactly when the markup is.
    assert type(rendered.to_svg_py()) is type(other.to_svg_py())
    assert rendered.to_svg_py() == rendered.to_svg_py()
    assert rendered.to_svg_py() != other.to_svg_py()
    assert len({rendered.to_svg_py(), rendered.to_svg_py(), other.to_svg_py()}) == 2


def test_drawsvg_adapter_is_insertable_and_serializes(simple_svg: bytes) -> None:
    rendered = fragment(simple_svg)
    element = rendered.to_drawsvg()
    assert isinstance(element, drawsvg.Raw)
    drawing = drawsvg.Drawing(rendered.width, rendered.height)
    drawing.append(element)
    assert rendered.to_svg() in drawing.as_svg()
