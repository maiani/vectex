"""Immutable public fragment value object."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from lxml import etree

from . import adapters


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
    def metadata(self) -> dict[str, Any]:
        """Return an independent deep copy of versioned render metadata."""
        value: dict[str, Any] = json.loads(self._metadata_json)
        return copy.deepcopy(value)

    def to_svg(self) -> str:
        """Serialize the canonical `<g>` deterministically."""
        return self._serialized.decode("utf-8")

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

    def to_svg_py(self) -> Any:
        """Return an insertable svg.py-compatible wrapper."""
        return adapters.to_svg_py(self.to_svg())

    def to_drawsvg(self) -> Any:
        """Return an insertable drawsvg-compatible wrapper."""
        return adapters.to_drawsvg(self.to_svg())
