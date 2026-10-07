"""Lossless wrappers for optional SVG object-model backends."""

from __future__ import annotations

from functools import cache
from typing import Any

from .exceptions import UnsupportedBackendError


@cache
def _svg_py_group() -> type:
    """The svg.py wrapper class, defined once so that wrappers compare by content."""
    try:
        import svg
    except ImportError as exc:
        raise UnsupportedBackendError(
            "svg.py is not installed; install vectex[svg-py]"
        ) from exc

    class VectexSvgPyGroup(svg.Element):
        element_name = "g"

        def __init__(self, content: str) -> None:
            self._vectex_content = content

        def as_str(self) -> str:
            return self._vectex_content

        # svg.py compares dataclass fields, and the markup is not one of them.
        def __eq__(self, other: object) -> bool:
            if not isinstance(other, VectexSvgPyGroup):
                return NotImplemented
            return self._vectex_content == other._vectex_content

        def __hash__(self) -> int:
            return hash(self._vectex_content)

    return VectexSvgPyGroup


def to_svg_py(serialized: str) -> Any:
    """Return an ``svg.Element`` that serializes the canonical group verbatim."""
    return _svg_py_group()(serialized)


def to_drawsvg(serialized: str) -> Any:
    """Return a ``drawsvg.Raw`` element containing the canonical group."""
    try:
        import drawsvg
    except ImportError as exc:
        raise UnsupportedBackendError(
            "drawsvg is not installed; install vectex[drawsvg]"
        ) from exc
    return drawsvg.Raw(serialized)
