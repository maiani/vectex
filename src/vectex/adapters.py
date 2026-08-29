"""Lossless wrappers for optional SVG object-model backends."""

from __future__ import annotations

from typing import Any

from .exceptions import UnsupportedBackendError


def to_svg_py(serialized: str) -> Any:
    """Return an ``svg.Element`` that serializes the canonical group verbatim."""
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

    return VectexSvgPyGroup(serialized)


def to_drawsvg(serialized: str) -> Any:
    """Return a ``drawsvg.Raw`` element containing the canonical group."""
    try:
        import drawsvg  # type: ignore[import-untyped]
    except ImportError as exc:
        raise UnsupportedBackendError(
            "drawsvg is not installed; install vectex[drawsvg]"
        ) from exc
    return drawsvg.Raw(serialized)
