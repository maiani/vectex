"""Secure conversion of SVG documents into portable group fragments."""

from __future__ import annotations

import copy
import json
import math
import re
import uuid
from collections.abc import Mapping
from typing import Any

from lxml import etree

from .exceptions import ConfigurationError, InvalidSVGError, UnsafeSVGError
from .fragment import VectexFragment

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
VECTEX_NS = "https://vectex.dev/ns/metadata/1"
TEXTEXT_NS = "http://www.iki.fi/pav/software/textext/"
METADATA_VERSION = "1"
TEXTEXT_COMPAT_VERSION = "1.13.0"

_UNSAFE_ELEMENTS = frozenset(
    {
        "animate",
        "animateMotion",
        "animateTransform",
        "foreignObject",
        "iframe",
        "script",
        "set",
        "style",
    }
)
_ROOT_EXCLUDED_ATTRIBUTES = frozenset(
    {"data-baseline", "height", "preserveAspectRatio", "version", "viewBox", "width"}
)
_URL_RE = re.compile(
    r"url\(\s*(?P<quote>['\"]?)(?P<target>.*?)(?P=quote)\s*\)", re.IGNORECASE
)
_PREFIX_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_INVALID_XML_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
_NUMBER_RE = re.compile(
    r"^[\t\n\r ]*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?:px)?[\t\n\r ]*$"
)


class Normalizer:
    """Normalize trusted converter output while enforcing fragment safety."""

    def normalize(
        self,
        svg: str | bytes,
        *,
        source: str,
        engine: str,
        converter: str,
        scale: float = 1.0,
        baseline: float | None = None,
        compiler_options: Mapping[str, Any] | None = None,
        converter_options: Mapping[str, Any] | None = None,
        id_prefix: str | None = None,
        textext_compatible: bool = True,
        textext_source: str | None = None,
        textext_preamble_file: str = "",
        textext_alignment: str = "middle center",
    ) -> VectexFragment:
        """Return one safe, self-contained SVG group."""
        _validate_xml_text(source, "source")
        _validate_xml_text(engine, "engine")
        _validate_xml_text(converter, "converter")
        _validate_xml_text(textext_source, "textext_source")
        _validate_xml_text(textext_preamble_file, "textext_preamble_file")
        _validate_xml_text(textext_alignment, "textext_alignment")
        scale = _positive_number(scale, "scale")
        if baseline is not None and not math.isfinite(baseline):
            raise ConfigurationError("baseline must be finite when provided")
        prefix = _id_prefix(id_prefix)
        root = _parse_svg(svg)
        _qualify_svg_namespace(root)
        min_x, min_y, source_width, source_height = _view_box(root)
        if baseline is None:
            baseline = _optional_number(root.get("data-baseline"), "data-baseline")

        fragment_id = f"{prefix}-root"
        id_map = _validate_and_map(root, prefix=prefix, root_id=fragment_id)
        _rewrite_references(root, id_map)

        width = source_width * scale
        height = source_height * scale
        view_box = (0.0, 0.0, width, height)
        compiler_data = dict(compiler_options or {})
        converter_data = dict(converter_options or {})
        metadata = {
            "baseline": baseline,
            "compiler_options": compiler_data,
            "converter": converter,
            "converter_options": converter_data,
            "engine": engine,
            "height": height,
            "scale": scale,
            "source": source,
            "version": METADATA_VERSION,
            "view_box": list(view_box),
            "width": width,
        }
        metadata_json = _json(metadata)

        nsmap: dict[str | None, str] = {
            None: SVG_NS,
            "vectex": VECTEX_NS,
        }
        if textext_compatible:
            nsmap["textext"] = TEXTEXT_NS
        if any(key == f"{{{XLINK_NS}}}href" for el in root.iter() for key in el.attrib):
            nsmap["xlink"] = XLINK_NS
        group = etree.Element(f"{{{SVG_NS}}}g", nsmap=nsmap)
        group.set("id", fragment_id)
        if textext_compatible:
            _add_textext_attributes(
                group,
                source=textext_source if textext_source is not None else source,
                engine=engine,
                converter=converter,
                scale=scale,
                preamble_file=textext_preamble_file,
                alignment=textext_alignment,
            )
        group.append(_metadata_element(metadata))

        viewport = etree.SubElement(group, f"{{{SVG_NS}}}g")
        matrix = (
            scale,
            0.0,
            0.0,
            scale,
            -scale * min_x,
            -scale * min_y,
        )
        viewport.set("transform", f"matrix({' '.join(_number(v) for v in matrix)})")
        for key, value in root.attrib.items():
            local = etree.QName(key).localname
            if local in _ROOT_EXCLUDED_ATTRIBUTES or local == "id":
                continue
            if local == "transform":
                viewport.set("transform", f"{viewport.get('transform')} {value}")
            else:
                viewport.set(key, value)
        for child in root:
            if (
                isinstance(child.tag, str)
                and etree.QName(child).localname == "metadata"
            ):
                continue
            viewport.append(copy.deepcopy(child))

        _clean_whitespace(group)
        _sort_attributes(group)
        serialized = etree.tostring(
            group,
            encoding="utf-8",
            xml_declaration=False,
            pretty_print=False,
        )
        return VectexFragment(
            _serialized=serialized,
            source=source,
            engine=engine,
            converter=converter,
            scale=scale,
            width=width,
            height=height,
            view_box=view_box,
            baseline=baseline,
            _metadata_json=metadata_json,
        )


def _parse_svg(svg: str | bytes) -> etree._Element:
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=False,
        remove_comments=True,
        remove_pis=True,
        huge_tree=False,
    )
    try:
        root = etree.fromstring(
            svg.encode("utf-8") if isinstance(svg, str) else svg, parser
        )
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise InvalidSVGError(f"Cannot parse converter SVG: {exc}") from exc
    if not isinstance(root.tag, str) or etree.QName(root).localname != "svg":
        raise InvalidSVGError("Converter output must have one <svg> document root")
    namespace = etree.QName(root).namespace
    if namespace not in (None, SVG_NS):
        raise InvalidSVGError(f"Unexpected SVG root namespace: {namespace!r}")
    return root


def _qualify_svg_namespace(root: etree._Element) -> None:
    for element in root.iter():
        if not isinstance(element.tag, str):
            raise InvalidSVGError("Entity and processing nodes are not supported")
        qname = etree.QName(element)
        if qname.namespace is None:
            element.tag = f"{{{SVG_NS}}}{qname.localname}"


def _view_box(root: etree._Element) -> tuple[float, float, float, float]:
    raw = root.get("viewBox")
    if raw is not None:
        parts = re.split(r"[\s,]+", raw.strip())
        if len(parts) != 4:
            raise InvalidSVGError("viewBox must contain exactly four numbers")
        try:
            values = tuple(float(part) for part in parts)
        except ValueError as exc:
            raise InvalidSVGError("viewBox contains a non-numeric value") from exc
        if not all(math.isfinite(value) for value in values):
            raise InvalidSVGError("viewBox values must be finite")
        min_x, min_y, width, height = values
    else:
        min_x = min_y = 0.0
        width = _svg_length(root.get("width"), "width")
        height = _svg_length(root.get("height"), "height")
    if width <= 0 or height <= 0:
        raise InvalidSVGError("SVG viewport width and height must be positive")
    return min_x, min_y, width, height


def _validate_and_map(
    root: etree._Element, *, prefix: str, root_id: str
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    next_id = 0
    for element in root.iter():
        local = etree.QName(element).localname
        if local in _UNSAFE_ELEMENTS:
            raise UnsafeSVGError(f"Unsafe or unsupported SVG element: <{local}>")
        for key, value in element.attrib.items():
            attr_local = etree.QName(key).localname
            if attr_local.lower().startswith("on"):
                raise UnsafeSVGError(
                    f"Event-handler attribute {attr_local!r} is not allowed"
                )
            if attr_local == "class":
                raise UnsafeSVGError(
                    "CSS class attributes are not allowed because destination "
                    "document styles could affect the fragment"
                )
            if attr_local == "href" and not value.startswith("#"):
                raise UnsafeSVGError(
                    f"External resource reference is not allowed: {value!r}"
                )
            for match in _URL_RE.finditer(value):
                target = match.group("target").strip()
                if not target.startswith("#"):
                    raise UnsafeSVGError(
                        f"External CSS resource is not allowed: {target!r}"
                    )
            if attr_local == "style" and "@import" in value.lower():
                raise UnsafeSVGError("CSS @import is not allowed")
        old_id = element.get("id")
        if old_id is None:
            continue
        if old_id in mapping:
            raise InvalidSVGError(f"Duplicate SVG id: {old_id!r}")
        new_id = root_id if element is root else f"{prefix}-{next_id}"
        next_id += element is not root
        mapping[old_id] = new_id
    return mapping


def _rewrite_references(root: etree._Element, mapping: Mapping[str, str]) -> None:
    for element in root.iter():
        old_id = element.get("id")
        if old_id is not None:
            element.set("id", mapping[old_id])
        for key, value in tuple(element.attrib.items()):
            if etree.QName(key).localname == "href":
                target = value[1:]
                element.set(key, f"#{_mapped(target, mapping)}")
                continue

            def replace_url(match: re.Match[str]) -> str:
                target = match.group("target").strip()[1:]
                return f"url(#{_mapped(target, mapping)})"

            element.set(key, _URL_RE.sub(replace_url, value))


def _mapped(target: str, mapping: Mapping[str, str]) -> str:
    try:
        return mapping[target]
    except KeyError as exc:
        raise InvalidSVGError(f"Unresolved internal SVG reference: #{target}") from exc


def _metadata_element(metadata: Mapping[str, Any]) -> etree._Element:
    wrapper = etree.Element(f"{{{SVG_NS}}}metadata")
    record = etree.SubElement(wrapper, f"{{{VECTEX_NS}}}fragment")
    for key in ("version", "engine", "converter", "scale", "width", "height"):
        record.set(
            key,
            _number(metadata[key])
            if isinstance(metadata[key], float)
            else str(metadata[key]),
        )
    record.set("viewBox", " ".join(_number(v) for v in metadata["view_box"]))
    if metadata["baseline"] is not None:
        record.set("baseline", _number(metadata["baseline"]))
    source_element = etree.SubElement(record, f"{{{VECTEX_NS}}}source")
    source_element.text = str(metadata["source"])
    options = etree.SubElement(record, f"{{{VECTEX_NS}}}options")
    compiler = etree.SubElement(options, f"{{{VECTEX_NS}}}compiler")
    compiler.set("encoding", "json")
    compiler.text = _json(metadata["compiler_options"])
    converter = etree.SubElement(options, f"{{{VECTEX_NS}}}converter")
    converter.set("encoding", "json")
    converter.text = _json(metadata["converter_options"])
    return wrapper


def _add_textext_attributes(
    group: etree._Element,
    *,
    source: str,
    engine: str,
    converter: str,
    scale: float,
    preamble_file: str,
    alignment: str,
) -> None:
    attributes = {
        "alignment": alignment,
        "jacobian_sqrt": "1.0",
        "pdfconverter": converter,
        "preamble": preamble_file,
        "scale": _number(scale),
        "texconverter": engine,
        "text": source.encode("unicode_escape").decode("utf-8"),
        "version": TEXTEXT_COMPAT_VERSION,
    }
    for key, value in attributes.items():
        group.set(f"{{{TEXTEXT_NS}}}{key}", value)


def _clean_whitespace(element: etree._Element) -> None:
    for child in element:
        _clean_whitespace(child)
        if child.tail is not None and not child.tail.strip():
            child.tail = None
    if len(element) and element.text is not None and not element.text.strip():
        element.text = None


def _sort_attributes(element: etree._Element) -> None:
    if element.attrib:
        items = sorted(element.attrib.items())
        element.attrib.clear()
        element.attrib.update(items)
    for child in element:
        _sort_attributes(child)


def _id_prefix(value: str | None) -> str:
    prefix = value or f"vx-{uuid.uuid4().hex[:12]}"
    if not _PREFIX_RE.fullmatch(prefix):
        raise ConfigurationError(
            "id_prefix must start with a letter or underscore and contain only "
            "XML id characters"
        )
    return prefix


def _validate_xml_text(value: str | None, option: str) -> None:
    if value is not None and _INVALID_XML_RE.search(value):
        raise ConfigurationError(f"{option} contains a character forbidden by XML 1.0")


def _positive_number(value: float, option: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{option} must be a positive finite number") from exc
    if not math.isfinite(number) or number <= 0:
        raise ConfigurationError(f"{option} must be a positive finite number")
    return number


def _optional_number(value: str | None, name: str) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise InvalidSVGError(f"{name} must be numeric") from exc
    if not math.isfinite(number):
        raise InvalidSVGError(f"{name} must be finite")
    return number


def _svg_length(value: str | None, name: str) -> float:
    if value is None:
        raise InvalidSVGError(f"SVG requires viewBox or numeric {name}")
    match = _NUMBER_RE.fullmatch(value)
    if match is None:
        raise InvalidSVGError(f"Cannot derive viewport from SVG {name}={value!r}")
    return float(match.group(1))


def _number(value: Any) -> str:
    return format(float(value), ".15g")


def _json(value: Any) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("metadata options must be JSON serializable") from exc
