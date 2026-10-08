from __future__ import annotations

import drawsvg
import pytest
import svg

from vectex import ConfigurationError, Normalizer


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
    element = rendered.to_svg_py(unit="pt")
    assert isinstance(element, svg.Element)
    assert str(element) == rendered.to_svg()


def test_adapters_scale_to_css_px_by_default(simple_svg: bytes) -> None:
    rendered = fragment(simple_svg)
    scaled = f'<g transform="scale(1.33333333333333)">{rendered.to_svg()}</g>'
    assert str(rendered.to_svg_py()) == scaled
    drawing = drawsvg.Drawing(rendered.width_px, rendered.height_px)
    drawing.append(rendered.to_drawsvg())
    assert scaled in drawing.as_svg()
    assert rendered.width_px == pytest.approx(rendered.width * 96 / 72)
    assert rendered.height_px == pytest.approx(rendered.height * 96 / 72)
    assert rendered.baseline_px is None or rendered.baseline_px == pytest.approx(
        rendered.baseline * 96 / 72
    )
    with pytest.raises(ConfigurationError, match="unit"):
        rendered.to_svg_py(unit="mm")


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


def placed(rendered, **where) -> tuple[float, float]:
    """Where a placed wrapper puts the fragment's top-left corner, in px."""
    markup = str(rendered.to_svg_py(**where))
    assert markup.endswith(f'scale(1.33333333333333)">{rendered.to_svg()}</g>')
    if "translate(" not in markup:
        return 0.0, 0.0
    left, top = markup.split("translate(", 1)[1].split(")", 1)[0].split()
    return float(left), float(top)


def test_a_wrapper_can_be_placed_by_any_point_of_its_box(simple_svg: bytes) -> None:
    rendered = Normalizer().normalize(
        simple_svg, source="x", engine="pdflatex", converter="dvisvgm", baseline=3.0
    )
    w, h = rendered.width_px, rendered.height_px
    assert placed(rendered) == (0.0, 0.0)
    assert placed(rendered, x=10, y=20) == (10, 20)
    assert placed(
        rendered, x=10, y=20, anchor="middle", valign="bottom"
    ) == pytest.approx((10 - w / 2, 20 - h))
    assert placed(rendered, x=10, y=20, anchor="end", valign="middle") == pytest.approx(
        (10 - w, 20 - h / 2)
    )
    assert placed(rendered, x=10, y=20, valign="baseline") == pytest.approx(
        (10, 20 - rendered.baseline_px)
    )
    in_points = str(rendered.to_svg_py(unit="pt", x=4, valign="baseline"))
    assert in_points == f'<g transform="translate(4 -3)">{rendered.to_svg()}</g>'
    drawing = drawsvg.Drawing(100, 100)
    drawing.append(rendered.to_drawsvg(x=10, y=20))
    assert str(rendered.to_svg_py(x=10, y=20)) in drawing.as_svg()


def test_placement_options_are_checked(simple_svg: bytes) -> None:
    rendered = fragment(simple_svg)
    assert rendered.baseline is None
    with pytest.raises(ConfigurationError, match="baseline"):
        rendered.to_svg_py(valign="baseline")
    with pytest.raises(ConfigurationError, match="anchor"):
        rendered.to_svg_py(anchor="left")
    with pytest.raises(ConfigurationError, match="valign"):
        rendered.to_drawsvg(valign="center")
