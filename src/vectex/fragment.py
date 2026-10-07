"""Immutable public fragment value object."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any

from lxml import etree

from . import adapters
from .exceptions import ConfigurationError

_SVG_NAMESPACE = "http://www.w3.org/2000/svg"
# Geometry is in TeX points, dvisvgm's user unit; CSS has 96 px per 72 pt.
_PX_PER_PT = 96 / 72


@dataclass(frozen=True, slots=True)
class VectexFragment:
    """One normalized SVG group and its editable render information."""

    _serialized: bytes
    source: str
    engine: str
    converter: str
    scale: float
    width: float
    height: float
    view_box: tuple[float, float, float, float]
    baseline: float | None
    _metadata_json: str

    @property
    def width_px(self) -> float:
        """Width in CSS px, the user unit of svg.py and drawsvg documents."""
        return self.width * _PX_PER_PT

    @property
    def height_px(self) -> float:
        """Height in CSS px, the user unit of svg.py and drawsvg documents."""
        return self.height * _PX_PER_PT

    @property
    def baseline_px(self) -> float | None:
        """Baseline below the top edge in CSS px, or ``None`` when unmeasured."""
        return None if self.baseline is None else self.baseline * _PX_PER_PT

    @property
    def metadata(self) -> dict[str, Any]:
        """Return an independent deep copy of versioned render metadata."""
        value: dict[str, Any] = json.loads(self._metadata_json)
        return copy.deepcopy(value)

    def to_svg(self) -> str:
        """Serialize the canonical `<g>` deterministically."""
        return self._serialized.decode("utf-8")

    def to_svg_document(self) -> str:
        """Return a standalone SVG document embedding the canonical group.

        Unlike :meth:`to_svg`, which returns only the portable ``<g>``
        fragment, this returns a complete document ready to open, serve, or
        save, without an SVG object-model backend.
        """
        min_x, min_y, _, _ = self.view_box
        view_box = " ".join(
            _number(value) for value in (min_x, min_y, self.width, self.height)
        )
        # Geometry is in TeX points (dvisvgm's user unit). A unitless length
        # would read as CSS px, drawing every label at 3/4 of its size.
        width = f"{_number(self.width)}pt"
        height = f"{_number(self.height)}pt"
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="{_SVG_NAMESPACE}" '
            f'width="{width}" height="{height}" viewBox="{view_box}">\n'
            f"{self.to_svg()}\n"
            "</svg>\n"
        )

    def write_svg_document(self, path: str | PathLike[str]) -> None:
        """Write the standalone SVG document from :meth:`to_svg_document`."""
        Path(path).write_text(self.to_svg_document(), encoding="utf-8")

    def to_lxml(self) -> etree._Element:
        """Return a fresh mutable lxml group, never the canonical element."""
        parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            load_dtd=False,
            recover=False,
            remove_comments=True,
            remove_pis=True,
        )
        return etree.fromstring(self._serialized, parser=parser)

    def to_svg_py(self, *, unit: str = "px") -> Any:
        """Return an insertable svg.py-compatible wrapper.

        With ``unit="px"`` (the default) the label is scaled from TeX points
        to CSS px, the user unit of an svg.py document, so it keeps its size
        there; it is then ``width_px`` by ``height_px``.  ``unit="pt"`` gives
        the canonical group unscaled.
        """
        return adapters.to_svg_py(self._markup(unit))

    def to_drawsvg(self, *, unit: str = "px") -> Any:
        """Return an insertable drawsvg-compatible wrapper, in px by default."""
        return adapters.to_drawsvg(self._markup(unit))

    def _markup(self, unit: str) -> str:
        if unit == "pt":
            return self.to_svg()
        if unit == "px":
            return f'<g transform="scale({_number(_PX_PER_PT)})">{self.to_svg()}</g>'
        raise ConfigurationError(f"unit must be 'px' or 'pt', got {unit!r}")


def _number(value: float) -> str:
    return format(float(value), ".15g")
