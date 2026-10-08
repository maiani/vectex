from __future__ import annotations

import re
from pathlib import Path

import pytest
from lxml import etree

from vectex import (
    TEXTEXT_NS,
    VECTEX_NS,
    ConfigurationError,
    InvalidSVGError,
    Normalizer,
    UnsafeSVGError,
)

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


def normalize(svg: bytes, **options: object):
    defaults = {
        "source": "E = mc^2",
        "engine": "pdflatex",
        "converter": "dvisvgm",
        "id_prefix": "fixture",
    }
    defaults.update(options)
    return Normalizer().normalize(svg, **defaults)


def test_one_group_and_view_box_normalization(complex_svg: bytes) -> None:
    fragment = normalize(complex_svg, scale=2.0)
    root = fragment.to_lxml()

    assert etree.QName(root).namespace == SVG_NS
    assert etree.QName(root).localname == "g"
    assert fragment.width == 24.0
    assert fragment.height == 16.0
    assert fragment.view_box == (0.0, 0.0, 24.0, 16.0)
    viewport = root.find(f"{{{SVG_NS}}}g")
    assert viewport is not None
    assert viewport.get("id") == "fixture-viewport"
    assert viewport.get("transform") == "matrix(2 0 0 2 4 -6)"


def test_nested_definitions_and_all_reference_forms_are_rewritten(
    complex_svg: bytes,
) -> None:
    root = normalize(complex_svg).to_lxml()
    ids = {element.get("id") for element in root.iter() if element.get("id")}

    assert ids == {
        "fixture-root",
        "fixture-viewport",
        "fixture-0",
        "fixture-1",
        "fixture-2",
        "fixture-3",
        "fixture-4",
    }
    values = [value for element in root.iter() for value in element.attrib.values()]
    # Numbered by first use: the clip path, then the glyph it draws.
    assert "#fixture-1" in values
    assert "url(#fixture-0)" in values
    assert any("url(#fixture-3)" in value for value in values)
    xlink_hrefs = root.xpath("//@xlink:href", namespaces={"xlink": XLINK_NS})
    assert xlink_hrefs == ["#fixture-1"]
    assert not re.search(r"(?<!fixture-)#(?:glyph|clip|gradient)", fragment_xml(root))


def test_pruning_retains_a_referenced_nested_definition() -> None:
    raw = (
        f'<svg xmlns="{SVG_NS}" viewBox="0 0 1 1">'
        '<defs><g id="unused-wrapper"><path id="glyph" d="M0 0h1v1z"/></g></defs>'
        '<use href="#glyph"/></svg>'
    ).encode()
    root = normalize(raw).to_lxml()
    href = root.xpath("//*[local-name()='use']/@href")
    assert href == ["#fixture-1"]
    assert root.xpath("//*[@id='fixture-1']")


def test_definitions_are_ordered_by_first_use_whatever_the_converter_order() -> None:
    # dvisvgm writes a batch page's glyphs in an order that varies between runs.
    glyphs = {
        "g3-1": '<path id="g3-1" d="M0 0h1"/>',
        "g0-5": '<path id="g0-5" d="M0 0h2"/>',
        "g1-1": '<path id="g1-1" d="M0 0h3"/>',
        "g2-9": '<path id="g2-9" d="M0 0h4"/>',
        "clip": '<clipPath id="clip"><use href="#g2-9"/></clipPath>',
    }
    body = (
        '<use href="#g0-5"/><use href="#g3-1" clip-path="url(#clip)"/>'
        '<use href="#g1-1"/><use href="#g0-5"/>'
    )

    def rendered(order: tuple[str, ...]) -> str:
        defs = "".join(glyphs[name] for name in order)
        raw = f'<svg xmlns="{SVG_NS}" viewBox="0 0 1 1"><defs>{defs}</defs>{body}</svg>'
        return normalize(raw.encode()).to_svg()

    first = rendered(("g3-1", "g0-5", "g1-1", "g2-9", "clip"))
    assert rendered(("clip", "g1-1", "g2-9", "g0-5", "g3-1")) == first
    assert rendered(("g0-5", "g3-1", "clip", "g2-9", "g1-1")) == first
    root = etree.fromstring(first)
    defs = root.find(f".//{{{SVG_NS}}}defs")
    assert defs is not None
    assert [child.get("d") or child.get("id") for child in defs] == [
        "M0 0h2",
        "M0 0h1",
        "fixture-2",
        "M0 0h4",
        "M0 0h3",
    ]


def test_unsafe_unused_definition_is_rejected() -> None:
    raw = (
        f'<svg xmlns="{SVG_NS}" viewBox="0 0 1 1">'
        '<defs><script id="unused">alert(1)</script></defs>'
        '<path d="M0 0h1v1z"/></svg>'
    ).encode()
    with pytest.raises(UnsafeSVGError, match="script"):
        normalize(raw)


def test_fragments_have_disjoint_default_id_namespaces(complex_svg: bytes) -> None:
    first = Normalizer().normalize(
        complex_svg, source="x", engine="pdflatex", converter="dvisvgm"
    )
    second = Normalizer().normalize(
        complex_svg, source="x", engine="pdflatex", converter="dvisvgm"
    )
    first_ids = {el.get("id") for el in first.to_lxml().iter() if el.get("id")}
    second_ids = {el.get("id") for el in second.to_lxml().iter() if el.get("id")}
    assert first_ids.isdisjoint(second_ids)


def test_deterministic_serialization_with_fixed_namespace(complex_svg: bytes) -> None:
    first = normalize(complex_svg)
    second = normalize(complex_svg)
    assert first.to_svg() == first.to_svg()
    assert first.to_svg() == second.to_svg()


def test_metadata_and_textext_round_trip_special_source(simple_svg: bytes) -> None:
    source = 'line 1: a < b & c > d\nline 2: "α" \\beta'  # noqa: RUF001
    fragment = normalize(
        simple_svg,
        source=source,
        scale=1.25,
        compiler_options={"preamble": "\\usepackage{amsmath}"},
        converter_options={"args": ["--exact"]},
        textext_source=f"\\(\\displaystyle {source}\\)",
        textext_preamble_file="/opt/vectex/packages.tex",
    )
    root = fragment.to_lxml()
    source_node = root.find(f".//{{{VECTEX_NS}}}source")
    assert source_node is not None
    assert source_node.text == source
    assert fragment.metadata["source"] == source
    assert fragment.metadata["compiler_options"] == {
        "preamble": "\\usepackage{amsmath}"
    }

    encoded = root.get(f"{{{TEXTEXT_NS}}}text")
    assert encoded is not None
    assert encoded.encode("utf-8").decode("unicode_escape") == (
        f"\\(\\displaystyle {source}\\)"
    )
    assert root.get(f"{{{TEXTEXT_NS}}}preamble") == "/opt/vectex/packages.tex"
    assert root.get(f"{{{TEXTEXT_NS}}}scale") == "1.25"
    assert root.get(f"{{{TEXTEXT_NS}}}texconverter") == "pdflatex"
    assert root.get(f"{{{TEXTEXT_NS}}}alignment") == "middle center"


def test_textext_compatibility_can_be_disabled(simple_svg: bytes) -> None:
    root = normalize(simple_svg, textext_compatible=False).to_lxml()
    assert not any(etree.QName(key).namespace == TEXTEXT_NS for key in root.attrib)


def test_baseline_from_converter_or_explicit_value() -> None:
    raw = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2 3" '
        b'data-baseline="2.5"><path d="M0 0"/></svg>'
    )
    assert normalize(raw).baseline == 2.5
    assert normalize(raw, baseline=1.25).baseline == 1.25
    assert normalize(raw, baseline_ratio=0.5, scale=2).baseline == 5


def test_default_black_follows_current_color_and_authored_colour_is_kept() -> None:
    raw = (
        f'<svg xmlns="{SVG_NS}" viewBox="0 0 2 2">'
        '<path id="black" fill="#000" d="M0 0"/>'
        '<path id="red" fill="#f00" d="M1 1"/>'
        '<path id="rule" fill="none" stroke="black" d="M0 1H2"/>'
        '<path id="styled" style="fill: #000000; stroke:rgb(0, 0, 0)" d="M0 2"/>'
        '<path id="plain" d="M2 2"/>'
        "</svg>"
    ).encode()
    root = normalize(raw).to_lxml()
    black, red, rule, styled, plain = (
        root.xpath(f".//*[@id='fixture-{i}']")[0] for i in range(5)
    )
    # Glyphs with no fill inherit the root's, which follows the CSS colour too.
    assert root.get("fill") == "currentColor"
    assert root.get("color") is None
    assert black.get("fill") == "currentColor"
    assert red.get("fill") == "#f00"
    # Rules -- fraction bars, radicals -- are strokes and recolour with glyphs.
    assert (rule.get("fill"), rule.get("stroke")) == ("none", "currentColor")
    assert styled.get("style") == "fill:currentColor;stroke:currentColor"
    assert plain.get("fill") is None


def test_color_sets_the_css_colour_of_the_whole_label() -> None:
    raw = f'<svg xmlns="{SVG_NS}" viewBox="0 0 1 1"><path d="M0 0"/></svg>'.encode()
    assert normalize(raw, color="#7a1fa2").to_lxml().get("color") == "#7a1fa2"
    assert normalize(raw, color=" rgb(10%, 20%, 30%) ").to_lxml().get("color") == (
        "rgb(10%, 20%, 30%)"
    )
    for bad in ("", "red; fill: blue", 'red" onload="x', 3):
        with pytest.raises(ConfigurationError, match="color"):
            normalize(raw, color=bad)


def test_lxml_returns_independent_copies(simple_svg: bytes) -> None:
    fragment = normalize(simple_svg)
    first = fragment.to_lxml()
    second = fragment.to_lxml()
    first.set("changed", "yes")
    first[1].clear()
    assert second.get("changed") is None
    assert "changed" not in fragment.to_svg()


@pytest.mark.parametrize(
    "body, message",
    [
        ("<script>alert(1)</script>", "script"),
        ("<foreignObject><div/></foreignObject>", "foreignObject"),
        ("<style>.x { fill: red }</style>", "style"),
        ('<path onload="alert(1)"/>', "Event-handler"),
        ('<image href="https://example.com/a.png"/>', "External resource"),
        ('<path style="fill:url(https://example.com/a.svg#x)"/>', "External CSS"),
        ('<path style="fill:url( https://example.com/a.svg#x )"/>', "External CSS"),
        ('<path class="destination-style"/>', "CSS class"),
        ('<animate attributeName="x"/>', "animate"),
    ],
)
def test_unsafe_svg_is_rejected(body: str, message: str) -> None:
    raw = f'<svg xmlns="{SVG_NS}" viewBox="0 0 10 10">{body}</svg>'
    with pytest.raises(UnsafeSVGError, match=message):
        normalize(raw.encode())


def test_unresolved_internal_reference_is_rejected() -> None:
    raw = f'<svg xmlns="{SVG_NS}" viewBox="0 0 1 1"><use href="#missing"/></svg>'
    with pytest.raises(InvalidSVGError, match="Unresolved"):
        normalize(raw.encode())


@pytest.mark.parametrize(
    "raw, message",
    [
        (b"<g/>", "<svg>"),
        (f'<svg xmlns="{SVG_NS}" viewBox="0 0 -1 2"/>'.encode(), "positive"),
        (f'<svg xmlns="{SVG_NS}" width="2pt" height="3pt"/>'.encode(), "derive"),
        (f'<svg xmlns="{SVG_NS}" viewBox="0 0 nope 2"/>'.encode(), "non-numeric"),
        (b"<svg>", "parse"),
    ],
)
def test_invalid_svg_is_rejected(raw: bytes, message: str) -> None:
    with pytest.raises(InvalidSVGError, match=message):
        normalize(raw)


@pytest.mark.parametrize("scale", [0, -1, float("inf"), float("nan")])
def test_invalid_scale_is_rejected(simple_svg: bytes, scale: float) -> None:
    with pytest.raises(ConfigurationError, match="scale"):
        normalize(simple_svg, scale=scale)


def test_to_svg_document_is_a_standalone_svg(simple_svg: bytes) -> None:
    fragment = normalize(simple_svg)
    document = fragment.to_svg_document()

    assert document.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert fragment.to_svg() in document
    root = etree.fromstring(document.encode())
    assert etree.QName(root).localname == "svg"
    assert root.get("width").endswith("pt"), "a unitless length would read as px"
    width, height = (
        float(root.get(key).removesuffix("pt")) for key in ("width", "height")
    )
    assert (width, height) == pytest.approx((fragment.width, fragment.height))
    assert tuple(float(part) for part in root.get("viewBox").split(" ")) == (
        fragment.view_box
    )
    assert root.find(f"{{{SVG_NS}}}g").get("id") == "fixture-root"


def test_write_svg_document_writes_the_standalone_svg(
    tmp_path: Path, simple_svg: bytes
) -> None:
    fragment = normalize(simple_svg)
    target = tmp_path / "label.svg"

    fragment.write_svg_document(target)

    assert target.read_text(encoding="utf-8") == fragment.to_svg_document()
    saved = etree.parse(target)
    assert etree.QName(saved.getroot()).localname == "svg"


def test_xml_forbidden_source_is_rejected(simple_svg: bytes) -> None:
    with pytest.raises(ConfigurationError, match="forbidden by XML"):
        normalize(simple_svg, source="bad\x00source")


def fragment_xml(root: etree._Element) -> str:
    return etree.tostring(root, encoding="unicode")
